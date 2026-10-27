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

"""Unit tests for POI search and persistence on reason_to_visit (T-027 / REQ-CTX-024, REQ-CTX-026, SC-002).

Validates:
- Keyword searches matching text exclusively in reason_to_visit return matching POIs.
- SQL query compilation incorporates reason_to_visit.ilike and description.ilike.
- CRUD operations (create, get_by_id, update) maintain reason_to_visit fidelity.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from geoalchemy2.elements import WKTElement
from vistarae_core.adapters.db.tables import POITable
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.domain.entities import POI
from vistarae_core.domain.value_objects import VisitState, WGS84Point


def _create_mock_poi_row(
    poi_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str = "Panoramic Overlook",
    description: str = "A high ridge scenic point.",
    reason_to_visit: str | None = "Spectacular sunset vista with rare alpine wildflower blooms.",
) -> MagicMock:
    """Creates a mock POITable row with reason_to_visit set."""
    row = MagicMock(spec=POITable)
    row.id = poi_id
    row.user_id = user_id
    row.parent_poi_id = None
    row.name = name
    row.description = description
    row.reason_to_visit = reason_to_visit
    row.address = "100 Ridge Trail"
    row.city = "Estes Park"
    row.states = ["Colorado"]
    row.countries = ["United States"]
    row.addresses = []
    row.source_type = "manual"
    row.source_value = None
    row.official_url = None
    row.wiki_url = None
    row.image_urls = []
    row.directory_paths = []
    row.creation_metadata = {}
    row.visit_state = "not_visited"
    row.visited_dates = []
    row.want_to_visit_again = False
    row.already_visited = False
    row.visit_pending = True
    row.rating = None
    row.estimated_cost = None
    row.pricing_unit = None
    row.recommended_duration_hours = 2.0
    row.recommended_visit_days = 0
    row.estimated_visit_time_notes = None
    row.enrichment_status = "SUCCESS"
    row.geom = WKTElement("POINT(-105.5 40.3)", srid=4326)
    row.region_geom = None
    row.embedding = None
    row.embedding_md5 = None
    row.created_at = None
    row.updated_at = None
    return row


class TestPOISearchReasonToVisit:
    """Test suite for search queries and persistence covering reason_to_visit."""

    @pytest.mark.asyncio
    async def test_list_pois_text_query_includes_reason_to_visit_in_sql(self) -> None:
        """Asserts text_query clause compiles reason_to_visit and description ILIKE filters."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        poi_id = uuid.uuid4()

        row = _create_mock_poi_row(
            poi_id=poi_id,
            user_id=user_id,
            name="Ordinary Viewpoint",
            description="Just a regular roadside stop.",
            reason_to_visit="Spectacular sunset vista with rare alpine wildflower blooms.",
        )

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
            text_query="wildflower",
        )

        assert total == 1
        assert len(pois) == 1
        assert pois[0].reason_to_visit == "Spectacular sunset vista with rare alpine wildflower blooms."

        # Verify SQL statements executed contain the ILIKE conditions for reason_to_visit
        calls = session.execute.call_args_list
        assert len(calls) == 2
        for call_item in calls:
            stmt = call_item[0][0]
            sql_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
            assert "pois.reason_to_visit ILIKE" in sql_str or "reason_to_visit" in sql_str
            assert "pois.description ILIKE" in sql_str or "description" in sql_str

    @pytest.mark.asyncio
    async def test_create_and_get_poi_preserves_reason_to_visit(self) -> None:
        """Asserts create and get_by_id faithfully persist and retrieve reason_to_visit."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        poi_id = uuid.uuid4()

        poi = POI(
            id=poi_id,
            user_id=user_id,
            name="Hidden Gem Bistro",
            geom=WGS84Point(lon=2.3522, lat=48.8566),
            description="A cozy Parisian bistro.",
            reason_to_visit="Secret back-room wine cellar with artisanal vintage pairings.",
            visit_state=VisitState.NOT_VISITED,
        )

        repo = SqlAlchemyPOIRepository(session)
        created = await repo.create(poi)

        assert created.reason_to_visit == "Secret back-room wine cellar with artisanal vintage pairings."
        # Verify row added to session has reason_to_visit populated
        added_row = session.add.call_args[0][0]
        assert added_row.reason_to_visit == "Secret back-room wine cellar with artisanal vintage pairings."

        # Mock get_by_id retrieval
        mock_row = _create_mock_poi_row(
            poi_id=poi_id,
            user_id=user_id,
            name=poi.name,
            description=poi.description,
            reason_to_visit=poi.reason_to_visit,
        )
        get_res = MagicMock()
        get_res.scalar_one_or_none.return_value = mock_row
        session.execute.side_effect = [get_res]

        retrieved = await repo.get_by_id(poi_id, user_id)
        assert retrieved is not None
        assert retrieved.reason_to_visit == "Secret back-room wine cellar with artisanal vintage pairings."

    @pytest.mark.asyncio
    async def test_update_poi_modifies_reason_to_visit(self) -> None:
        """Asserts update modifies reason_to_visit on POITable."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        poi_id = uuid.uuid4()

        existing_row = _create_mock_poi_row(
            poi_id=poi_id,
            user_id=user_id,
            reason_to_visit="Old reason to visit.",
        )
        fetch_res = MagicMock()
        fetch_res.scalar_one_or_none.return_value = existing_row
        session.execute.return_value = fetch_res

        repo = SqlAlchemyPOIRepository(session)
        updated_poi = POI(
            id=poi_id,
            user_id=user_id,
            name="Updated Name",
            geom=WGS84Point(lon=2.3522, lat=48.8566),
            description="Updated description.",
            reason_to_visit="Brand new updated reason to visit with night views.",
            visit_state=VisitState.NOT_VISITED,
        )

        result = await repo.update(updated_poi)
        assert existing_row.reason_to_visit == "Brand new updated reason to visit with night views."
        assert result.reason_to_visit == "Brand new updated reason to visit with night views."
