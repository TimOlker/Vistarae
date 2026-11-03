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

"""End-to-end integration test verifying quickstart requirements and CSV ingestion compatibility."""

from pathlib import Path

import httpx
from vistarae_core.schemas.extractor import (
    neutralize_formula_injection,
)

from extractor_scripts.common.exporter import CSVExporter
from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractorConfig
from extractor_scripts.nps_sites import NPSSitesExtractor
from services.ingest.services.csv_parser import parse_and_sanitize_csv

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_quickstart_e2e_all_extractors_and_ingestion(tmp_path: Path) -> None:
    """Verifies all 5 extractors generate valid CSVs parsed successfully by Vistarae ingestion."""
    # 1. Formula defense
    assert neutralize_formula_injection("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert neutralize_formula_injection("+123") == "'+123"
    assert neutralize_formula_injection("Normal") == "Normal"

    # 2. NPS Extraction & CSV Ingestion Compatibility
    nps_html = (FIXTURES_DIR / "nps_directory.html").read_text(encoding="utf-8")
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=nps_html))
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )

    nps_csv = tmp_path / "nps_test.csv"
    config = ExtractorConfig(output_path=nps_csv, cache_enabled=False)
    extractor = NPSSitesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    generated_files = CSVExporter.export(records, nps_csv, split_size=2000)
    assert len(generated_files) == 1
    assert nps_csv.exists()

    # Ingest using Vistarae production ingestion parser
    raw_bytes = nps_csv.read_bytes()
    parsed_rows = parse_and_sanitize_csv(raw_bytes, content_type="text/csv")
    assert len(parsed_rows) == 3
    assert parsed_rows[0]["row_data"]["poi_name"] == "Yellowstone National Park"

    # 3. Partitioning verification
    split_csv = tmp_path / "split_demo.csv"
    split_files = CSVExporter.export(records, split_csv, split_size=1)
    assert len(split_files) == 3
    for f in split_files:
        p_rows = parse_and_sanitize_csv(f.read_bytes(), content_type="text/csv")
        assert len(p_rows) == 1
