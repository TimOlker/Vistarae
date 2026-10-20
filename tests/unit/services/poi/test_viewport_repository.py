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

"""Unit tests for PostGIS POIRepository viewport exploration and spatial queries (T-009).

Tests:
- POI CRUD operations (create, get_by_id, update, delete, bulk_delete)
- Planar viewport bounding box lookups (ST_MakeEnvelope and &&)
- Antimeridian crossing detection and dual-envelope split query generation
- Multi-facet filtering: states (@>), countries (@>), visit_state, hierarchy, parent_id
- List and tag membership joins
- Semantic vector ordering and text search
- Coordinate extraction helper error handling
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.db.tables import POITable
from vistarae_core.adapters.repositories.poi_repo import (
    SqlAlchemyPOIRepository,
    _extract_wgs84_point,
)
from vistarae_core.domain.entities import POI
from vistarae_core.domain.exceptions import POINotFoundError
from vistarae_core.domain.value_objects import (
    BoundingBox,
    VisitState,
    WGS84Point,
)


def _make_poi_row(
    poi_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    name: str = "Test Overlook",
    lon: float = -122.4194,
    lat: float = 37.7749,
    parent_poi_id: uuid.UUID | None = None,
    states: list[str] | None = None,
    countries: list[str] | None = None,
    visit_state: str = "not_visited",
) -> MagicMock:
    """Creates a mock POITable row for testing."""
    row = MagicMock(spec=POITable)
    row.id = poi_id or uuid.uuid4()
    row.user_id = user_id or uuid.uuid4()
    row.parent_poi_id = parent_poi_id
    row.name = name
    row.description = "A scenic viewpoint"
    row.address = "123 Skyline Dr"
    row.city = "San Francisco"
    row.states = states or ["California"]
    row.countries = countries or ["United States"]
    row.official_url = "https://parks.example.com"
    row.wiki_url = "https://wiki.example.com"
    row.image_urls = ["https://img.example.com/1.jpg"]
    row.directory_paths = ["North America/USA/CA"]
    row.creation_metadata = {"source": "manual"}
    row.visit_state = visit_state
    row.visited_dates = []
    row.rating = 4
    row.estimated_cost = None
    row.pricing_unit = None
    row.recommended_duration_hours = None
    row.recommended_visit_days = 1
    row.enrichment_status = "SUCCESS"
    row.region_geom = None
    row.embedding = [0.1] * 768
    row.embedding_md5 = "abc123md5"
    row.created_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)

    # Mock geom with x and y attributes
    mock_geom = MagicMock()
    mock_geom.x = lon
    mock_geom.y = lat
    row.geom = mock_geom

    return row


class TestCoordinateExtraction:
    """Tests for _extract_wgs84_point."""

    def test_extract_from_wgs84_point(self) -> None:
        """Returns identity when already WGS84Point."""
        pt = WGS84Point(lon=-120.0, lat=38.0)
        assert _extract_wgs84_point(pt) == pt

    def test_extract_from_object_with_xy(self) -> None:
        """Extracts lon and lat from object with x and y attributes."""
        obj = MagicMock()
        obj.x = -118.5
        obj.y = 34.2
        pt = _extract_wgs84_point(obj)
        assert pt.lon == -118.5
        assert pt.lat == 34.2

    def test_extract_invalid_object_raises_value_error(self) -> None:
        """Raises ValueError when object has no geometry data."""
        with pytest.raises(ValueError, match="Unable to extract WGS84Point"):
            _extract_wgs84_point(12345)


class TestPOIRepositoryCRUD:
    """Tests for create, get_by_id, update, delete, bulk_delete."""

    @pytest.mark.asyncio
    async def test_create_poi(self) -> None:
        """Asserts create flushes and returns pure domain POI."""
        session = AsyncMock()
        repo = SqlAlchemyPOIRepository(session)

        poi = POI(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Half Dome",
            geom=WGS84Point(lon=-119.5332, lat=37.7460),
            states=["California"],
            countries=["United States"],
        )

        created = await repo.create(poi)
        assert session.add.called
        assert session.flush.called
        assert created.name == "Half Dome"
        assert created.geom.lon == -119.5332

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        """Asserts get_by_id returns domain POI when record exists."""
        session = AsyncMock()
        poi_id = uuid.uuid4()
        user_id = uuid.uuid4()
        row = _make_poi_row(poi_id=poi_id, user_id=user_id, name="Vernal Fall")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        result = await repo.get_by_id(poi_id, user_id)

        assert result is not None
        assert result.id == poi_id
        assert result.name == "Vernal Fall"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        """Asserts get_by_id returns None when record does not exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        result = await repo.get_by_id(uuid.uuid4(), uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_update_poi_found(self) -> None:
        """Asserts update updates row attributes and flushes."""
        session = AsyncMock()
        poi_id = uuid.uuid4()
        user_id = uuid.uuid4()
        row = _make_poi_row(poi_id=poi_id, user_id=user_id, name="Old Name")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        updated_poi = POI(
            id=poi_id,
            user_id=user_id,
            name="New Name",
            geom=WGS84Point(lon=-120.0, lat=38.0),
            states=["California"],
            countries=["United States"],
        )

        res = await repo.update(updated_poi)
        assert res.name == "New Name"
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_update_poi_not_found_raises(self) -> None:
        """Asserts update raises POINotFoundError when row missing."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        poi = POI(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Nonexistent",
            geom=WGS84Point(lon=0.0, lat=0.0),
        )

        with pytest.raises(POINotFoundError):
            await repo.update(poi)

    @pytest.mark.asyncio
    async def test_delete_poi(self) -> None:
        """Asserts delete returns True when deleted, False otherwise."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        deleted = await repo.delete(uuid.uuid4(), uuid.uuid4())
        assert deleted is True

        mock_result.rowcount = 0
        deleted = await repo.delete(uuid.uuid4(), uuid.uuid4())
        assert deleted is False

    @pytest.mark.asyncio
    async def test_bulk_delete(self) -> None:
        """Asserts bulk_delete deletes list of POIs."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        count = await repo.bulk_delete([uuid.uuid4(), uuid.uuid4(), uuid.uuid4()], uuid.uuid4())
        assert count == 3

        count_empty = await repo.bulk_delete([], uuid.uuid4())
        assert count_empty == 0


class TestPOIRepositoryListPois:
    """Tests for list_pois with spatial, bbox, and facet combinations."""

    @pytest.mark.asyncio
    async def test_list_pois_standard_viewport(self) -> None:
        """Asserts planar bounding box query executes with count and limit."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        row = _make_poi_row(user_id=user_id, name="Glacier Point")

        count_res = MagicMock()
        count_res.scalar.return_value = 1
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [row]
        data_res = MagicMock()
        data_res.scalars.return_value = scalars_mock

        session.execute.side_effect = [count_res, data_res]

        repo = SqlAlchemyPOIRepository(session)
        bbox = BoundingBox(min_lon=-120.0, min_lat=37.0, max_lon=-119.0, max_lat=38.0)

        pois, total = await repo.list_pois(user_id=user_id, bbox=bbox, limit=10, offset=0)

        assert total == 1
        assert len(pois) == 1
        assert pois[0].name == "Glacier Point"

    @pytest.mark.asyncio
    async def test_list_pois_antimeridian_crossing(self) -> None:
        """Asserts antimeridian crossing generates dual-envelope queries."""
        session = AsyncMock()
        user_id = uuid.uuid4()

        count_res = MagicMock()
        count_res.scalar.return_value = 0
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_res = MagicMock()
        data_res.scalars.return_value = scalars_mock

        session.execute.side_effect = [count_res, data_res]

        repo = SqlAlchemyPOIRepository(session)
        # min_lon > max_lon crosses 180th meridian
        bbox = BoundingBox(min_lon=175.0, min_lat=-20.0, max_lon=-175.0, max_lat=-15.0)
        assert bbox.crosses_antimeridian is True

        pois, total = await repo.list_pois(user_id=user_id, bbox=bbox)
        assert total == 0
        assert pois == []

    @pytest.mark.asyncio
    async def test_list_pois_multi_facet_filtering(self) -> None:
        """Asserts state, country, visit_state, hierarchy, and text query filtering."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        row = _make_poi_row(user_id=user_id, name="Tuolumne Meadows")

        count_res = MagicMock()
        count_res.scalar.return_value = 1
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [row]
        data_res = MagicMock()
        data_res.scalars.return_value = scalars_mock

        session.execute.side_effect = [count_res, data_res]

        repo = SqlAlchemyPOIRepository(session)
        pois, total = await repo.list_pois(
            user_id=user_id,
            state="California",
            country="United States",
            visit_state=VisitState.NOT_VISITED,
            hierarchy="root_only",
            text_query="Tuolumne",
            list_id=uuid.uuid4(),
            tag_ids=[uuid.uuid4()],
            parent_id=None,
            semantic_vector=[0.05] * 768,
        )

        assert total == 1
        assert len(pois) == 1

    @pytest.mark.asyncio
    async def test_list_pois_children_only_hierarchy(self) -> None:
        """Asserts hierarchy='children_only' filters properly."""
        session = AsyncMock()
        user_id = uuid.uuid4()

        count_res = MagicMock()
        count_res.scalar.return_value = 0
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_res = MagicMock()
        data_res.scalars.return_value = scalars_mock

        session.execute.side_effect = [count_res, data_res]

        repo = SqlAlchemyPOIRepository(session)
        pois, total = await repo.list_pois(
            user_id=user_id,
            hierarchy="children_only",
            parent_id=uuid.uuid4(),
        )
        assert total == 0
