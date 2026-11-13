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

"""Integration test for intra-batch nesting reconstruction (017-export T-014).

Validates:
- Intra-batch parent candidate hierarchy re-linking via UUID translation map (FR-011)
- Intra-batch merge target re-linking via UUID translation map (FR-011)
- User disposition and override preservation bypassing heuristic recalculation (FR-007)
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.domain.value_objects import IngestDisposition
from vistarae_core.schemas.poi_export import POIExportRecord

from services.ingest.services.staging_service import StagingService


@pytest.fixture
def mock_candidate_repo() -> MagicMock:
    repo = MagicMock()
    repo.create_batch = AsyncMock(side_effect=lambda candidates: candidates)
    repo.list_by_job = AsyncMock(return_value=[])
    repo.get_candidate = AsyncMock(return_value=None)
    repo.update_candidate = AsyncMock(side_effect=lambda user_id, cand: cand)
    return repo


@pytest.fixture
def mock_ingest_repo() -> MagicMock:
    repo = MagicMock()
    repo.append_duplicate_payload = AsyncMock()
    repo.increment_processed_rows = AsyncMock()
    repo.update_job_status = AsyncMock()
    repo.append_error_summary = AsyncMock()
    return repo


class TestReimportNestingIntegration:
    """Integration tests for UUID translation table resolution during staging."""

    @pytest.mark.asyncio
    async def test_uuid_translation_map_reconstructs_parent_and_merge_targets(
        self,
        mock_candidate_repo: MagicMock,
        mock_ingest_repo: MagicMock,
    ) -> None:
        """Asserts exported candidate IDs are mapped to newly generated DB UUIDs for parent and merge links."""
        service = StagingService(
            candidate_repo=mock_candidate_repo,
            ingest_repo=mock_ingest_repo,
        )

        user_id = uuid4()
        job_id = uuid4()

        exported_id_parent = uuid4()
        exported_id_sub = uuid4()
        exported_id_merge = uuid4()

        records = [
            POIExportRecord(
                poi_name="Grand Canyon National Park",
                latitude=Decimal("36.0544"),
                longitude=Decimal("-112.1401"),
                street_address=["South Rim"],
                town_city=["Grand Canyon Village"],
                state_province=["Arizona"],
                country=["United States"],
                photo_directory="/photos/grand_canyon",
                location_confidence_percent=100,
                candidate_id=exported_id_parent,
                row_index=0,
                user_disposition=IngestDisposition.ACCEPT,
                is_user_overridden=True,
            ),
            POIExportRecord(
                poi_name="Mather Point",
                latitude=Decimal("36.0562"),
                longitude=Decimal("-112.1077"),
                street_address=["Desert View Dr"],
                town_city=["Grand Canyon Village"],
                state_province=["Arizona"],
                country=["United States"],
                photo_directory="/photos/mather_point",
                location_confidence_percent=95,
                candidate_id=exported_id_sub,
                parent_candidate_id=exported_id_parent,
                row_index=1,
                user_disposition=IngestDisposition.SUBLOCATION,
                disposition_justification="Overlook nested in South Rim",
                is_user_overridden=True,
            ),
            POIExportRecord(
                poi_name="Mather Pt",
                latitude=Decimal("36.0562"),
                longitude=Decimal("-112.1077"),
                street_address=["Desert View Dr"],
                town_city=["Grand Canyon Village"],
                state_province=["Arizona"],
                country=["United States"],
                photo_directory="/photos/mather_pt",
                location_confidence_percent=90,
                candidate_id=exported_id_merge,
                merge_target_id=exported_id_sub,
                row_index=2,
                user_disposition=IngestDisposition.IN_BATCH_MERGE,
                disposition_justification="Typo duplicate of Mather Point",
                is_user_overridden=True,
            ),
        ]

        staged = await service.stage_records(user_id=user_id, job_id=job_id, records=records)

        assert len(staged) == 3
        cand_parent, cand_sub, cand_merge = staged[0], staged[1], staged[2]

        # Assert new DB UUIDs generated (differ from exported ones)
        assert cand_parent.id != exported_id_parent
        assert cand_sub.id != exported_id_sub
        assert cand_merge.id != exported_id_merge

        # Assert intra-batch hierarchy translated accurately to new DB UUIDs
        assert cand_sub.parent_candidate_id == cand_parent.id
        assert cand_merge.merge_target_id == cand_sub.id

        # Assert user dispositions and overrides preserved
        assert cand_parent.user_disposition == IngestDisposition.ACCEPT
        assert cand_parent.is_user_overridden is True

        assert cand_sub.user_disposition == IngestDisposition.SUBLOCATION
        assert cand_sub.disposition_justification == "Overlook nested in South Rim"
        assert cand_sub.is_user_overridden is True

        assert cand_merge.user_disposition == IngestDisposition.IN_BATCH_MERGE
        assert cand_merge.disposition_justification == "Typo duplicate of Mather Point"
        assert cand_merge.is_user_overridden is True
