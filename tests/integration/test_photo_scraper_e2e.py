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

"""End-to-end integration test for the photo scraper and two-phase ingestion pipeline (T-040).

Validates the complete workflow:
1. CLI Photo Scraper scans photo archive tree in read-only mode (zero mutations).
2. Metadata extractor parses EXIF / sidecar coordinates and earliest capture dates.
3. Location resolver populates standardized POI attributes.
4. Standardized CSV is exported with formula injection protection.
5. Ingestion CSV parser streams and validates records.
6. StagingService executes deduplication and stages candidates for Phase 1 triage.
7. Phase 1 advances non-ignored candidates to Phase 2.
8. Phase 2 enriches descriptions and reasons to visit with user style directives.
9. Final database commit persists POIs and executes multi-visit merges.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image
from vistarae_core.domain.entities import POI, IngestCandidate
from vistarae_core.domain.value_objects import (
    IngestDisposition,
    PromptType,
)
from vistarae_core.schemas.poi_export import POIExportRecord

from services.ingest.services.csv_parser import parse_and_sanitize_csv
from services.ingest.services.staging_service import StagingService
from services.scraper.photo_scraper import run_photo_scraper


def _compute_dir_hash(path: Path) -> str:
    """Computes SHA-256 hash across all files and paths in directory tree."""
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(path):
        dirs.sort()
        files.sort()
        for f in files:
            file_path = Path(root) / f
            hasher.update(str(file_path.relative_to(path)).encode("utf-8"))
            with open(file_path, "rb") as fp:
                while chunk := fp.read(65536):
                    hasher.update(chunk)
    return hasher.hexdigest()


@pytest.mark.asyncio
async def test_photo_scraper_e2e_pipeline() -> None:
    """Tests complete end-to-end photo scan, CSV export, staging, enrichment, and commit."""
    user_id = uuid4()
    job_id = uuid4()

    with tempfile.TemporaryDirectory() as tmp_root:
        root_path = Path(tmp_root)
        photo_dir = root_path / "photos"
        cache_dir = root_path / "cache"
        output_csv = root_path / "vistarae_pois.csv"

        # Create test photo archive
        sensoji_dir = photo_dir / "Trip To Japan" / "1-Sensoji"
        sensoji_dir.mkdir(parents=True, exist_ok=True)

        img = Image.new("RGB", (64, 64), color="red")
        img.save(str(sensoji_dir / "DSC_001.jpg"))

        # Create companion sidecar with coordinates
        xmp_content = """<?xml version="1.0"?>
        <x:xmpmeta xmlns:x="adobe:ns:meta/">
          <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
            <rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/">
              <exif:GPSLatitude>35.7147</exif:GPSLatitude>
              <exif:GPSLongitude>139.7966</exif:GPSLongitude>
              <exif:DateTimeOriginal>2023-04-10T14:30:00</exif:DateTimeOriginal>
            </rdf:Description>
          </rdf:RDF>
        </x:xmpmeta>"""
        with open(sensoji_dir / "DSC_001.xmp", "w", encoding="utf-8") as f:
            f.write(xmp_content)

        # Snapshot archive tree hash before scanning (REQ-SCR-001 immutability check)
        pre_scan_hash = _compute_dir_hash(photo_dir)

        # 1. Execute CLI photo scraper
        mock_ai_resp = MagicMock()
        mock_ai_resp.poi_name = "Senso-ji"
        mock_ai_resp.street = "2 Chome-3-1 Asakusa"
        mock_ai_resp.city = "Taito City"
        mock_ai_resp.state_province = "Tokyo"
        mock_ai_resp.postal_code = "111-0032"
        mock_ai_resp.country = "Japan"
        mock_ai_resp.location_confidence_percent = 95
        mock_ai_resp.confidence_rationale = "Recognized historic Asakusa Buddhist temple"

        with patch(
            "services.scraper.location_resolver.LocationResolver.resolve", return_value=mock_ai_resp
        ):
            exit_code = run_photo_scraper(
                input_dir=photo_dir,
                output_csv=output_csv,
                cache_db=cache_dir / ".scraper_cache.db",
                api_key="mock-api-key",
            )

        assert exit_code == 0
        assert output_csv.exists()

        # 2. Assert zero filesystem mutations on original photo archive (REQ-SCR-001, SC-002)
        post_scan_hash = _compute_dir_hash(photo_dir)
        assert pre_scan_hash == post_scan_hash, "Scanned directory was modified during scraper run"

        # 3. Read and parse exported CSV via ingestion parser
        with open(output_csv, "rb") as f:
            csv_bytes = f.read()

        raw_rows = parse_and_sanitize_csv(csv_bytes)
        assert len(raw_rows) == 1
        row = raw_rows[0]["row_data"]
        assert row["poi_name"] == "Senso-ji"
        assert row["country"] == "Japan"
        assert row["dates_visited"] == ["2023-04-10"]

        # Convert to POIExportRecord for staging
        parsed_records = [
            POIExportRecord(
                poi_name=row["poi_name"],
                street_address=[row["street_address"]] if row.get("street_address") else [],
                town_city=[row["city"]] if row.get("city") else [],
                state_province=[row["state_province"]] if row.get("state_province") else [],
                zip_code=[row["postal_code"]] if row.get("postal_code") else [],
                country=[row["country"]] if row.get("country") else [],
                latitude=Decimal(str(row["latitude"])) if row.get("latitude") is not None else None,
                longitude=Decimal(str(row["longitude"]))
                if row.get("longitude") is not None
                else None,
                dates_visited=row.get("dates_visited", []),
                photo_directory=row.get("photo_directory", ""),
                location_confidence_percent=row.get("confidence_score", 0),
            )
        ]

        # 4. Stage candidates in StagingService (Phase 1)
        staged_candidates: list[IngestCandidate] = []

        mock_candidate_repo = MagicMock()
        mock_candidate_repo.create_batch = AsyncMock(side_effect=lambda cands: cands)
        mock_candidate_repo.list_by_job = AsyncMock(
            side_effect=lambda uid, jid, state=None: staged_candidates
        )
        mock_candidate_repo.update_candidate = AsyncMock(side_effect=lambda uid, c: c)
        mock_candidate_repo.advance_to_phase2 = AsyncMock(return_value=1)
        mock_candidate_repo.purge_by_job = AsyncMock(return_value=1)

        persisted_pois: list[POI] = []
        mock_poi_repo = MagicMock()
        mock_poi_repo.create = AsyncMock(side_effect=lambda p: (persisted_pois.append(p), p)[1])
        mock_poi_repo.get_by_id = AsyncMock(return_value=None)
        mock_poi_repo.update = AsyncMock(side_effect=lambda p: p)

        staging_service = StagingService(
            candidate_repo=mock_candidate_repo,
            poi_repo=mock_poi_repo,
        )

        staged = await staging_service.stage_records(user_id, job_id, parsed_records)
        assert len(staged) == 1
        staged_candidates.extend(staged)
        assert staged[0].recommended_disposition == IngestDisposition.ACCEPT

        # 5. Advance Phase 1 to Phase 2
        adv, ign = await staging_service.advance_to_phase2(user_id, job_id)
        assert adv == 1
        assert ign == 0

        # 6. Phase 2 Enrichment with travel style directives
        directives = {
            PromptType.DESCRIPTION: "Highlight traditional wooden temple architecture.",
            PromptType.REASON_TO_VISIT: "Morning atmosphere and cultural photography.",
        }

        mock_orchestrator = MagicMock()
        mock_orchestrator.synthesize_summary = AsyncMock(
            return_value="Ancient Buddhist temple known for its iconic lantern and historic wooden pagoda."
        )
        mock_orchestrator.synthesize_reason_to_visit = AsyncMock(
            return_value="Tourists visit for morning atmosphere, authentic Edo culture, and architecture."
        )

        staging_service._orchestrator = mock_orchestrator

        enriched = await staging_service.enrich_candidates_phase2(
            user_id=user_id,
            job_id=job_id,
            prompt_directives=directives,
        )
        assert len(enriched) == 1
        assert "lantern" in enriched[0].description
        assert "Edo culture" in enriched[0].reason_to_visit

        # 7. Final Database Commit
        total, created_ids, merged_ids = await staging_service.commit_job(user_id, job_id)
        assert total == 1
        assert len(created_ids) == 1
        assert len(merged_ids) == 0

        # Assert POI persisted to database
        assert len(persisted_pois) == 1
        committed_poi = persisted_pois[0]
        assert committed_poi.name == "Senso-ji"
        assert committed_poi.geom.lat == 35.7147
        assert committed_poi.geom.lon == 139.7966
        assert committed_poi.visited_dates == ["2023-04-10"]
        assert "lantern" in committed_poi.description
        mock_candidate_repo.purge_by_job.assert_awaited_once_with(user_id, job_id)
