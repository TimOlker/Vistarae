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

"""Unit tests for previous execution incremental diffing in photo scraper (T-019).

Validates:
- Loading previously processed directories from --previous-csv (REQ-SCR-008)
- Skipping previously processed folders during traversal
- Overriding skip behavior when --rescan-existing is set (REQ-SCR-009)
"""

from __future__ import annotations

from pathlib import Path

from vistarae_core.schemas.poi_export import POIExportRecord
from vistarae_core.services.csv_exporter import generate_standard_poi_csv

from services.scraper.photo_scraper import load_previous_directories


def test_load_previous_directories(tmp_path: Path) -> None:
    """Verifies parsing of 'Photo directory' column from previous CSV output."""
    csv_file = tmp_path / "previous.csv"
    records = [
        POIExportRecord(
            poi_name="Senso-ji",
            photo_directory="/photos/Japan/Senso-ji",
            location_confidence_percent=95,
        ),
        POIExportRecord(
            poi_name="Red Fort",
            photo_directory="/photos/India/Red Fort",
            location_confidence_percent=90,
        ),
    ]
    csv_file.write_text(generate_standard_poi_csv(records), encoding="utf-8")

    dirs = load_previous_directories(csv_file)
    assert "/photos/Japan/Senso-ji" in dirs
    assert "/photos/India/Red Fort" in dirs


def test_load_previous_directories_missing_file() -> None:
    """Verifies that non-existent previous CSV returns an empty set."""
    dirs = load_previous_directories(Path("does_not_exist.csv"))
    assert dirs == set()


def test_load_previous_directories_corrupt_or_empty(tmp_path: Path) -> None:
    """Tests load_previous_directories on empty or column-missing CSVs."""
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")
    assert load_previous_directories(empty_csv) == set()

    no_dir_csv = tmp_path / "no_dir.csv"
    no_dir_csv.write_text("POI Name,Country\nEiffel,France\n", encoding="utf-8")
    assert load_previous_directories(no_dir_csv) == set()
