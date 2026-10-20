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

"""Unit tests for deduplication detection, cycle prevention, and interactive POI merge (T-015).

Tests:
- find_potential_duplicates: trigram similarity (similarity >= 0.60) + proximity filtering
- HierarchyService: cycle detection, self-parenting rejection, recursive ancestor loop guard
- merge_pois: atomic attribute migration, cascade re-parenting, list union, tag union
- TagLimitExceededError: enforcement of 30-tag ceiling during merge and bulk operations
- Error handling: POINotFoundError when target or source POI is missing
- Bulk association operations: bulk_attach_tags, bulk_detach_tags, bulk_attach_lists, bulk_detach_lists
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.db.tables import POITable
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.domain.exceptions import (
    CyclicHierarchyError,
    POINotFoundError,
    TagLimitExceededError,
)
from vistarae_core.domain.value_objects import (
    MergeResolutionRule,
    WGS84Point,
)
from vistarae_core.services.hierarchy import HierarchyService


def _make_poi_row(
    poi_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    name: str = "Glacier Point",
    lon: float = -119.5732,
    lat: float = 37.7304,
    parent_poi_id: uuid.UUID | None = None,
) -> MagicMock:
    """Creates a mock POITable row for testing."""
    row = MagicMock(spec=POITable)
    row.id = poi_id or uuid.uuid4()
    row.user_id = user_id or uuid.uuid4()
    row.parent_poi_id = parent_poi_id
    row.name = name
    row.description = "Iconic overlook"
    row.address = "Yosemite Valley"
    row.city = "Yosemite"
    row.states = ["California"]
    row.countries = ["United States"]
    row.official_url = "https://nps.gov/yose"
    row.wiki_url = None
    row.image_urls = []
    row.directory_paths = []
    row.creation_metadata = {}
    row.visit_state = "not_visited"
    row.visited_dates = []
    row.rating = 5
    row.estimated_cost = None
    row.pricing_unit = None
    row.recommended_duration_hours = None
    row.recommended_visit_days = 1
    row.enrichment_status = "SUCCESS"
    row.region_geom = None
    row.embedding = None
    row.embedding_md5 = None
    row.created_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)

    mock_geom = MagicMock()
    mock_geom.x = lon
    mock_geom.y = lat
    row.geom = mock_geom

    return row


class TestHierarchyServiceCyclePrevention:
    """Tests for HierarchyService cycle detection and DAG invariants (T-017)."""

    @pytest.mark.asyncio
    async def test_none_parent_is_valid(self) -> None:
        """Assigning None (root) never causes a cycle."""
        session = AsyncMock()
        service = HierarchyService(session)
        # Should not raise
        await service.validate_no_cycle(uuid.uuid4(), uuid.uuid4(), None)
        assert not session.execute.called

    @pytest.mark.asyncio
    async def test_self_parenting_raises_cyclic_error(self) -> None:
        """Assigning poi_id as its own parent raises CyclicHierarchyError."""
        session = AsyncMock()
        service = HierarchyService(session)
        same_id = uuid.uuid4()

        with pytest.raises(CyclicHierarchyError) as exc_info:
            await service.validate_no_cycle(uuid.uuid4(), same_id, same_id)

        assert exc_info.value.poi_id == str(same_id)
        assert exc_info.value.proposed_parent_id == str(same_id)
        assert not session.execute.called

    @pytest.mark.asyncio
    async def test_descendant_cycle_detected(self) -> None:
        """Detects indirect cycles when CTE query returns a matching row."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (uuid.uuid4(),)  # CTE found row
        session.execute.return_value = mock_result

        service = HierarchyService(session)
        poi_id = uuid.uuid4()
        proposed_parent = uuid.uuid4()

        with pytest.raises(CyclicHierarchyError) as exc_info:
            await service.validate_no_cycle(uuid.uuid4(), poi_id, proposed_parent)

        assert exc_info.value.poi_id == str(poi_id)

    @pytest.mark.asyncio
    async def test_valid_parenting_passes(self) -> None:
        """Passes cleanly when CTE finds no ancestor relationship."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None  # No cycle
        session.execute.return_value = mock_result

        service = HierarchyService(session)
        await service.validate_no_cycle(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert session.execute.called


class TestPOIRepositoryDeduplication:
    """Tests for find_potential_duplicates (T-016)."""

    @pytest.mark.asyncio
    async def test_find_potential_duplicates_with_matches(self) -> None:
        """Asserts candidate duplicate returns ranked matches with confidence."""
        session = AsyncMock()
        row = _make_poi_row(name="Glacier Point Overlook")

        # Mock result returning (POITable, distance_meters, name_similarity)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (row, 250.0, 0.88),
        ]
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        matches = await repo.find_potential_duplicates(
            user_id=uuid.uuid4(),
            name="Glacier Point",
            point=WGS84Point(lon=-119.5732, lat=37.7304),
            radius_meters=805.0,
            similarity_threshold=0.60,
        )

        assert len(matches) == 1
        assert matches[0].existing_poi.name == "Glacier Point Overlook"
        assert matches[0].distance_meters == 250.0
        assert matches[0].name_similarity == 0.88
        assert matches[0].match_confidence > 0.0

    @pytest.mark.asyncio
    async def test_find_potential_duplicates_empty(self) -> None:
        """Asserts returns empty list when no spatial collisions exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        repo = SqlAlchemyPOIRepository(session)
        matches = await repo.find_potential_duplicates(
            user_id=uuid.uuid4(),
            name="Unique Remote Mountain",
            point=WGS84Point(lon=0.0, lat=0.0),
            radius_meters=805.0,
        )
        assert matches == []


class TestPOIRepositoryMerge:
    """Tests for atomic interactive POI merge (T-018)."""

    @pytest.mark.asyncio
    async def test_merge_pois_success(self) -> None:
        """Asserts successful merge copies attributes, re-parents children, and deletes source."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        target_id = uuid.uuid4()
        source_id = uuid.uuid4()

        target_row = _make_poi_row(poi_id=target_id, user_id=user_id, name="Target POI")
        target_row.description = "Old description"
        source_row = _make_poi_row(poi_id=source_id, user_id=user_id, name="Source POI")
        source_row.description = "Enriched description from source"

        # Mock query returning both target and source rows
        fetch_res = MagicMock()
        fetch_scalars = MagicMock()
        fetch_scalars.all.return_value = [target_row, source_row]
        fetch_res.scalars.return_value = fetch_scalars

        # Mock CTE cycle check returning None (no cycle)
        cte_res = MagicMock()
        cte_res.first.return_value = None

        # Mock update for child re-parenting
        update_res = MagicMock()

        # Mock lists and tags queries
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        empty_res = MagicMock()
        empty_res.scalars.return_value = empty_scalars

        session.execute.side_effect = [
            fetch_res,  # fetch target and source
            cte_res,  # cycle detection CTE
            update_res,  # re-parent children
            empty_res,  # source lists
            empty_res,  # target lists
            empty_res,  # source tags
            empty_res,  # target tags
        ]

        repo = SqlAlchemyPOIRepository(session)
        rule = MergeResolutionRule(
            target_poi_id=target_id,
            source_poi_id=source_id,
            use_source_for=["description"],
            merge_tags=True,
        )

        merged = await repo.merge_pois(user_id=user_id, rule=rule)

        assert merged.id == target_id
        assert target_row.description == "Enriched description from source"
        assert session.delete.called
        assert session.delete.call_args[0][0] == source_row
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_merge_pois_missing_target_raises_not_found(self) -> None:
        """Asserts POINotFoundError when target POI missing."""
        session = AsyncMock()
        fetch_res = MagicMock()
        fetch_scalars = MagicMock()
        fetch_scalars.all.return_value = []
        fetch_res.scalars.return_value = fetch_scalars
        session.execute.return_value = fetch_res

        repo = SqlAlchemyPOIRepository(session)
        rule = MergeResolutionRule(
            target_poi_id=uuid.uuid4(),
            source_poi_id=uuid.uuid4(),
        )

        with pytest.raises(POINotFoundError):
            await repo.merge_pois(uuid.uuid4(), rule)

    @pytest.mark.asyncio
    async def test_merge_pois_tag_limit_exceeded_raises(self) -> None:
        """Asserts TagLimitExceededError when union of unique tags exceeds 30."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        target_id = uuid.uuid4()
        source_id = uuid.uuid4()

        target_row = _make_poi_row(poi_id=target_id, user_id=user_id)
        source_row = _make_poi_row(poi_id=source_id, user_id=user_id)

        fetch_res = MagicMock()
        fetch_scalars = MagicMock()
        fetch_scalars.all.return_value = [target_row, source_row]
        fetch_res.scalars.return_value = fetch_scalars

        cte_res = MagicMock()
        cte_res.first.return_value = None

        update_res = MagicMock()

        list_scalars = MagicMock()
        list_scalars.all.return_value = []
        list_res = MagicMock()
        list_res.scalars.return_value = list_scalars

        # 20 distinct tags on source, 15 distinct tags on target -> 35 total
        source_tag_ids = [uuid.uuid4() for _ in range(20)]
        target_tag_ids = [uuid.uuid4() for _ in range(15)]

        s_tag_scalars = MagicMock()
        s_tag_scalars.all.return_value = source_tag_ids
        s_tag_res = MagicMock()
        s_tag_res.scalars.return_value = s_tag_scalars

        t_tag_scalars = MagicMock()
        t_tag_scalars.all.return_value = target_tag_ids
        t_tag_res = MagicMock()
        t_tag_res.scalars.return_value = t_tag_scalars

        session.execute.side_effect = [
            fetch_res,
            cte_res,
            update_res,
            list_res,
            list_res,
            s_tag_res,
            t_tag_res,
        ]

        repo = SqlAlchemyPOIRepository(session)
        rule = MergeResolutionRule(
            target_poi_id=target_id,
            source_poi_id=source_id,
            merge_tags=True,
        )

        with pytest.raises(TagLimitExceededError) as exc_info:
            await repo.merge_pois(user_id, rule)

        assert exc_info.value.count == 35
        assert exc_info.value.limit == 30


class TestPOIRepositoryBulkOperations:
    """Tests for bulk_attach_tags, bulk_detach_tags, bulk_attach_lists, bulk_detach_lists."""

    @pytest.mark.asyncio
    async def test_bulk_attach_tags_success(self) -> None:
        """Asserts bulk_attach_tags validates ownership and attaches tags."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        poi_ids = [uuid.uuid4(), uuid.uuid4()]
        tag_ids = [uuid.uuid4()]

        count_res = MagicMock()
        count_res.scalar.return_value = 2  # Both POIs exist

        tag_count_res = MagicMock()
        tag_count_res.scalar.return_value = 5  # Currently 5 tags

        exists_res = MagicMock()
        exists_res.scalar_one_or_none.return_value = None  # Not already attached

        session.execute.side_effect = [
            count_res,
            tag_count_res,
            tag_count_res,
            exists_res,
            exists_res,
        ]

        repo = SqlAlchemyPOIRepository(session)
        created = await repo.bulk_attach_tags(user_id, poi_ids, tag_ids)
        assert created == 2
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_bulk_attach_tags_limit_exceeded(self) -> None:
        """Asserts bulk_attach_tags raises when tags exceed 30."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        poi_ids = [uuid.uuid4()]
        tag_ids = [uuid.uuid4() for _ in range(5)]

        count_res = MagicMock()
        count_res.scalar.return_value = 1

        tag_count_res = MagicMock()
        tag_count_res.scalar.return_value = 28  # 28 + 5 = 33 > 30

        session.execute.side_effect = [count_res, tag_count_res]

        repo = SqlAlchemyPOIRepository(session)
        with pytest.raises(TagLimitExceededError):
            await repo.bulk_attach_tags(user_id, poi_ids, tag_ids)

    @pytest.mark.asyncio
    async def test_bulk_detach_tags(self) -> None:
        """Asserts bulk_detach_tags returns deleted count."""
        session = AsyncMock()
        res = MagicMock()
        res.rowcount = 4
        session.execute.return_value = res

        repo = SqlAlchemyPOIRepository(session)
        count = await repo.bulk_detach_tags(uuid.uuid4(), [uuid.uuid4()], [uuid.uuid4()])
        assert count == 4

        count_empty = await repo.bulk_detach_tags(uuid.uuid4(), [], [])
        assert count_empty == 0

    @pytest.mark.asyncio
    async def test_bulk_attach_lists(self) -> None:
        """Asserts bulk_attach_lists creates list associations."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        poi_ids = [uuid.uuid4()]
        list_ids = [uuid.uuid4(), uuid.uuid4()]

        exists_res = MagicMock()
        exists_res.scalar_one_or_none.return_value = None
        session.execute.side_effect = [exists_res, exists_res]

        repo = SqlAlchemyPOIRepository(session)
        count = await repo.bulk_attach_lists(user_id, poi_ids, list_ids)
        assert count == 2
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_bulk_detach_lists(self) -> None:
        """Asserts bulk_detach_lists returns deleted count."""
        session = AsyncMock()
        res = MagicMock()
        res.rowcount = 2
        session.execute.return_value = res

        repo = SqlAlchemyPOIRepository(session)
        count = await repo.bulk_detach_lists(uuid.uuid4(), [uuid.uuid4()], [uuid.uuid4()])
        assert count == 2
