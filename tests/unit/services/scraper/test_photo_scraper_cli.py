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

"""Integration tests for standalone Photo Scraper CLI (T-014).

Validates:
- End-to-end recursive directory traversal (REQ-SCR-002)
- Zero filesystem mutations on media directories (REQ-SCR-001)
- 12-column standardized RFC 4180 CSV generation (REQ-SCR-035)
- Filtering of noise folders (bad, thumbs, RESOURCE.FRK, Tim) (REQ-SCR-004..007)
- Incremental skipping of previous CSV entries (REQ-SCR-008)
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from vistarae_core.schemas.poi_export import POIExportRecord
from vistarae_core.services.csv_exporter import generate_standard_poi_csv

from services.scraper.location_resolver import POIStandardizedLocationSchema
from services.scraper.photo_scraper import (
    _is_poi_directory,
    main,
    run_photo_scraper,
)


def _compute_dir_hash(directory: Path) -> str:
    """Computes SHA-256 tree hash to ensure read-only guarantee."""
    hasher = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            hasher.update(str(p.relative_to(directory)).encode())
            hasher.update(p.read_bytes())
    return hasher.hexdigest()


def test_photo_scraper_e2e_traversal(tmp_path: Path) -> None:
    """Runs full scraper against sample fixture directory and verifies output CSV."""
    fixture_dir = Path("tests/fixtures/sample_photos")
    output_csv = tmp_path / "output_pois.csv"
    cache_db = tmp_path / "test_cache.db"

    hash_before = _compute_dir_hash(fixture_dir)

    # Mock Gemini resolver to avoid external network calls during unit test
    def mock_resolve(path_context, latitude=None, longitude=None, tags=None):
        return POIStandardizedLocationSchema(
            poi_name=path_context.poi_name or "Resolved POI",
            street="123 Main St",
            city=path_context.city or "City",
            state_province=path_context.state_province or "State",
            postal_code="12345",
            country=path_context.country or "United States",
            location_confidence_percent=92,
        )

    with patch(
        "services.scraper.location_resolver.LocationResolver.resolve",
        side_effect=mock_resolve,
    ):
        exit_code = run_photo_scraper(
            input_dir=fixture_dir,
            output_csv=output_csv,
            cache_db=cache_db,
            api_key="mock-key",
        )

    assert exit_code == 0
    assert output_csv.exists()

    # Verify zero mutations
    hash_after = _compute_dir_hash(fixture_dir)
    assert hash_before == hash_after

    # Inspect generated CSV
    with open(output_csv, encoding="utf-8") as f:
        reader = list(csv.reader(f))

    assert len(reader) >= 4  # Header + Red Fort + Senso-ji + Monte Alban
    header = reader[0]
    assert header[0] == "POI Name"
    assert header[10] == "Photo directory"
    assert header[11] == "location_confidence_percent"

    poi_names = [row[0] for row in reader[1:]]
    assert "Red Fort" in poi_names
    assert "Senso-ji" in poi_names
    assert "Monte Alban" in poi_names

    # Noise folders must NOT appear
    for noise in ("bad", "thumbs", "Tim", "Maria", "RESOURCE.FRK", "New Folder (2)"):
        assert noise not in poi_names


def test_photo_scraper_incremental_diff(tmp_path: Path) -> None:
    """Verifies that directories in previous CSV are skipped."""
    fixture_dir = Path("tests/fixtures/sample_photos")
    output_csv = tmp_path / "output_diff.csv"
    cache_db = tmp_path / "test_cache.db"

    # Pre-populate previous CSV with Senso-ji directory
    prev_csv = tmp_path / "prev.csv"
    sensoji_dir = fixture_dir / "Japan 4-03" / "1-Tokyo" / "Senso-ji (Asakusa Kannon)"
    prev_record = POIExportRecord(
        poi_name="Senso-ji",
        photo_directory=str(sensoji_dir),
        location_confidence_percent=95,
    )
    prev_csv.write_text(generate_standard_poi_csv([prev_record]), encoding="utf-8")

    def mock_resolve(path_context, latitude=None, longitude=None, tags=None):
        return POIStandardizedLocationSchema(
            poi_name=path_context.poi_name,
            country="Country",
            location_confidence_percent=90,
        )

    with patch(
        "services.scraper.location_resolver.LocationResolver.resolve",
        side_effect=mock_resolve,
    ):
        exit_code = run_photo_scraper(
            input_dir=fixture_dir,
            output_csv=output_csv,
            cache_db=cache_db,
            previous_csv=prev_csv,
            api_key="mock-key",
        )

    assert exit_code == 0
    with open(output_csv, encoding="utf-8") as f:
        reader = list(csv.reader(f))

    poi_names = [row[0] for row in reader[1:]]
    # Senso-ji should have been skipped!
    assert "Senso-ji" not in poi_names
    assert "Red Fort" in poi_names
    assert "Monte Alban" in poi_names


def test_photo_scraper_cli_errors(tmp_path: Path) -> None:
    """Tests CLI error handling on invalid input dir."""
    res = run_photo_scraper(input_dir=tmp_path / "does_not_exist", api_key="dummy")
    assert res == 1


def test_photo_scraper_cli_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests CLI main entrypoint."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-mock-key")
    fixture_dir = Path("tests/fixtures/sample_photos")
    out_csv = tmp_path / "main_out.csv"
    cache_file = tmp_path / "main_cache.db"

    with patch("services.scraper.location_resolver.LocationResolver.resolve") as mock_res:
        mock_res.return_value = POIStandardizedLocationSchema(
            poi_name="Test",
            country="United States",
            location_confidence_percent=85,
        )
        with pytest.raises(SystemExit) as exc:
            main([
                "--input-dir", str(fixture_dir),
                "--output-csv", str(out_csv),
                "--cache-dir", str(cache_file),
            ])
        assert exc.value.code == 0


def test_is_poi_directory_empty(tmp_path: Path) -> None:
    """Tests directory without images."""
    assert _is_poi_directory(tmp_path) is False


def test_rescan_existing_override(tmp_path: Path) -> None:
    """Verifies that --rescan-existing re-evaluates folders in previous CSV."""
    fixture_dir = Path("tests/fixtures/sample_photos")
    output_csv = tmp_path / "output_rescan.csv"
    cache_db = tmp_path / "test_cache.db"

    prev_csv = tmp_path / "prev.csv"
    sensoji_dir = fixture_dir / "Japan 4-03" / "1-Tokyo" / "Senso-ji (Asakusa Kannon)"
    prev_record = POIExportRecord(
        poi_name="Senso-ji",
        photo_directory=str(sensoji_dir),
        location_confidence_percent=95,
    )
    prev_csv.write_text(generate_standard_poi_csv([prev_record]), encoding="utf-8")

    def mock_resolve(path_context, latitude=None, longitude=None, tags=None):
        return POIStandardizedLocationSchema(
            poi_name=path_context.poi_name,
            country="Country",
            location_confidence_percent=90,
        )

    with patch(
        "services.scraper.location_resolver.LocationResolver.resolve",
        side_effect=mock_resolve,
    ):
        exit_code = run_photo_scraper(
            input_dir=fixture_dir,
            output_csv=output_csv,
            cache_db=cache_db,
            previous_csv=prev_csv,
            rescan_existing=True,
            api_key="mock-key",
        )

    assert exit_code == 0
    with open(output_csv, encoding="utf-8") as f:
        reader = list(csv.reader(f))
    poi_names = [row[0] for row in reader[1:]]
    assert "Senso-ji" in poi_names
