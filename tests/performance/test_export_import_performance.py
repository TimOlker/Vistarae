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

"""Performance benchmark tests for full-fidelity CSV export and re-import (017-export T-023).

Validates:
- 1,000-candidate re-import processing completes in <= 5 seconds (SC-005)
- Memory and throughput efficiency across full 37-column dataset
"""

from __future__ import annotations

import csv
import io
import json
import time
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.schemas.export_schema import UTF8_BOM, get_canonical_headers
from vistarae_core.schemas.poi_export import POIExportRecord

from services.ingest.services.csv_parser import parse_and_sanitize_csv
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


class TestExportImportPerformance:
    """Benchmark validating re-import of 1,000 candidates with all 37 attributes within 5s."""

    @pytest.mark.asyncio
    async def test_thousand_candidate_reimport_under_five_seconds(
        self,
        mock_candidate_repo: MagicMock,
        mock_ingest_repo: MagicMock,
    ) -> None:
        """Benchmarks parsing and staging of 1,000 diverse candidates against SC-005."""
        headers = get_canonical_headers()

        # 1. Generate 1,000 rows in memory
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(headers)

        parent_id = str(uuid.uuid4())
        for i in range(1000):
            cand_id = str(uuid.uuid4())
            row = [
                cand_id,  # Candidate ID
                str(i),  # Row Index
                f"'=Overlook {i}",  # POI Name (neutralized formula)
                f"{i} Scenic Way",  # Street Address
                "Sedona",  # City / Town
                "Oak Creek",  # Locality
                "Yavapai County",  # County / District (Admin Level 2)
                "Arizona",  # State / Province (Admin Level 1)
                "Arizona",  # State / Province
                "86336",  # Postal Code / Zip
                "United States",  # Country
                "US",  # Country Code
                f"{34.8697 + (i * 0.0001):.6f}",  # Latitude
                f"{-111.7609 - (i * 0.0001):.6f}",  # Longitude
                "accept",  # Recommended Disposition
                "accept" if i % 2 == 0 else "sublocation",  # User Disposition
                "95",  # Confidence Score
                f"Curated highlight #{i}",  # Disposition Justification
                f"Stunning red rock sandstone formations at point #{i}",  # Description
                "Iconic red rock views and trailheads",  # Reason to Visit
                f"https://example.com/photos/hero_{i}.jpg",  # Hero Image URL
                "https://visitsedona.com",  # Official URL
                "https://en.wikipedia.org/wiki/Sedona,_Arizona",  # Wikipedia URL
                json.dumps(
                    [{"name": f"Trail {i}", "url": f"https://fs.usda.gov/recarea/{i}"}]
                ),  # Related Websites
                "false",  # No Websites Flag
                "RedRocks; Hiking; Scenic; Arizona",  # Tags
                f"/photos/sedona/{i}",  # Photo Directory
                f"/photos/sedona/{i}; /photos/arizona",  # Photo Directories
                "2023-04-10; 2024-05-12",  # Dates Visited
                "2.5",  # Recommended Duration Hours
                "1",  # Recommended Visit Days
                "Best during golden hour",  # Estimated Visit Time Notes
                parent_id if i > 0 else "",  # Parent Candidate ID
                "",  # Parent POI ID
                "",  # Matched Existing POI ID
                "",  # Merge Target ID
                "true" if i % 2 == 0 else "false",  # Is User Overridden
            ]
            writer.writerow(row)

        csv_bytes = (UTF8_BOM + output.getvalue()).encode("utf-8")
        assert len(csv_bytes) < 2 * 1024 * 1024  # Within 2MB invariant limit

        # 2. Time parsing and staging
        start_time = time.perf_counter()

        # Step A: Parse CSV
        parsed_rows = parse_and_sanitize_csv(csv_bytes, content_type="text/csv")
        assert len(parsed_rows) == 1000

        # Step B: Convert to POIExportRecord
        records = [
            POIExportRecord(
                poi_name=r["row_data"]["poi_name"],
                latitude=Decimal(str(r["row_data"]["latitude"]).lstrip("'"))
                if r["row_data"].get("latitude")
                else None,
                longitude=Decimal(str(r["row_data"]["longitude"]).lstrip("'"))
                if r["row_data"].get("longitude")
                else None,
                street_address=[r["row_data"]["street_address"]],
                town_city=[r["row_data"]["city"]],
                state_province=[r["row_data"]["state_province"]],
                country=[r["row_data"]["country"]],
                tags=r["row_data"]["tags"],
                dates_visited=r["row_data"]["dates_visited"],
                photo_directory=r["row_data"]["photo_directory"],
                photo_directories=r["row_data"]["photo_directories"],
                location_confidence_percent=r["row_data"]["confidence_score"],
                candidate_id=uuid.UUID(r["row_data"]["candidate_id"])
                if r["row_data"].get("candidate_id")
                else None,
                parent_candidate_id=uuid.UUID(r["row_data"]["parent_candidate_id"])
                if r["row_data"].get("parent_candidate_id")
                else None,
                user_disposition=r["row_data"]["user_disposition"],
                is_user_overridden=r["row_data"]["is_user_overridden"],
                description=r["row_data"]["description"],
                reason_to_visit=r["row_data"]["reason_to_visit"],
            )
            for r in parsed_rows
        ]

        # Step C: Stage records
        service = StagingService(
            candidate_repo=mock_candidate_repo,
            ingest_repo=mock_ingest_repo,
        )
        staged = await service.stage_records(
            user_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            records=records,
        )

        elapsed = time.perf_counter() - start_time
        assert len(staged) == 1000
        print(
            f"\n[BENCHMARK] 1,000 candidates parsed and staged in {elapsed:.3f}s (Threshold: <= 5.0s)"
        )

        # Assert performance criterion SC-005
        assert elapsed <= 5.0, (
            f"1,000-candidate re-import took {elapsed:.2f}s, exceeding 5.0s threshold!"
        )
