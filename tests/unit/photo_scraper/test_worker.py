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

"""Unit tests for photo scraper worker and CSV export (T-039).

Verifies:
- Formula prefix neutralization (=, +, -, @, \\t, \\r) during CSV generation
- CSV writing according to canonical Vistarae ingestion schema
- Non-interactive mode assigns triage_status = 'NEEDS_REVIEW' to uncertain POIs
- Interactive TTY prompts support Confirm [c], Edit [e], and Skip [s]
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from vistarae_core.schemas.ingest import PhotoPOIInference

from photo_scraper.core.worker import (
    PhotoScraperEngine,
    ScrapedPOIRow,
    sanitize_csv_field,
    write_ingestion_csv,
)


class TestPhotoWorkerUnit:
    """Test suite for photo scraper triage and CSV export."""

    def test_sanitize_csv_field_neutralizes_formulas(self) -> None:
        """Asserts formula injection characters are neutralized with leading quote."""
        assert sanitize_csv_field("=SUM(A1:B2)") == "'=SUM(A1:B2)"
        assert sanitize_csv_field("+12345") == "'+12345"
        assert sanitize_csv_field("-SUM(A1:A10)") == "'-SUM(A1:A10)"
        assert sanitize_csv_field("@SUM(B1:B5)") == "'@SUM(B1:B5)"
        assert sanitize_csv_field("\ttabbed") == "'\ttabbed"
        assert sanitize_csv_field("\rcarriage") == "'\rcarriage"
        assert sanitize_csv_field("Normal Overlook") == "Normal Overlook"
        assert sanitize_csv_field(None) == ""

    def test_write_ingestion_csv_canonical_format(self) -> None:
        """Asserts write_ingestion_csv formats headers and columns correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test_out.csv"
            rows = [
                ScrapedPOIRow(
                    name="=Formula Location",
                    description="Historic location",
                    address="123 Road",
                    city="Kyoto",
                    state="Kyoto",
                    country="Japan",
                    latitude=35.0,
                    longitude=135.0,
                    visited_date="2024-04-10",
                    tags="scenic",
                    triage_status="APPROVED",
                ),
                ScrapedPOIRow(
                    name="Generic Restaurant",
                    description="Dining establishment",
                    city="Kyoto",
                    country="Japan",
                    triage_status="NEEDS_REVIEW",
                ),
            ]

            count = write_ingestion_csv(rows, out_file)
            assert count == 2
            assert out_file.exists()

            with open(out_file, encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                assert headers == [
                    "name",
                    "description",
                    "address",
                    "city",
                    "state",
                    "country",
                    "latitude",
                    "longitude",
                    "visited_date",
                    "tags",
                    "triage_status",
                ]
                row1 = next(reader)
                assert row1[0] == "'=Formula Location"
                assert row1[10] == "APPROVED"

                row2 = next(reader)
                assert row2[0] == "Generic Restaurant"
                assert row2[10] == "NEEDS_REVIEW"

    def test_scan_and_export_non_interactive_assigns_needs_review(self) -> None:
        """Asserts uncertain POI in non-interactive mode receives NEEDS_REVIEW without prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            photo_dir = Path(tmpdir) / "photos"
            sub_dir = photo_dir / "2024" / "Japan" / "Dining"
            sub_dir.mkdir(parents=True)

            img_path = sub_dir / "IMG_101.JPG"
            img = Image.new("RGB", (10, 10))
            img.save(img_path)

            mock_parser = MagicMock()
            mock_parser.is_configured.return_value = True
            mock_parser.infer_poi.return_value = PhotoPOIInference(
                name="Kyoto Restaurant",
                description="Uncertain restaurant",
                city="Kyoto",
                country="Japan",
                confidence_score=0.55,
                is_uncertain=True,
            )

            out_csv = Path(tmpdir) / "output.csv"
            engine = PhotoScraperEngine(gemini_parser=mock_parser, dry_run=True)

            rows = engine.scan_and_export(
                photo_dir=photo_dir,
                output_csv=out_csv,
                non_interactive=True,
            )

            assert len(rows) == 1
            assert rows[0].name == "Kyoto Restaurant"
            assert rows[0].triage_status == "NEEDS_REVIEW"
            assert out_csv.exists()

    def test_scan_and_export_interactive_confirm(self) -> None:
        """Asserts interactive prompt [c] confirms POI as APPROVED."""
        with tempfile.TemporaryDirectory() as tmpdir:
            photo_dir = Path(tmpdir) / "photos"
            sub_dir = photo_dir / "2024" / "Kyoto"
            sub_dir.mkdir(parents=True)

            img_path = sub_dir / "IMG_202.JPG"
            Image.new("RGB", (10, 10)).save(img_path)

            mock_parser = MagicMock()
            mock_parser.is_configured.return_value = True
            mock_parser.infer_poi.return_value = PhotoPOIInference(
                name="Airport Hotel",
                description="Transit hotel",
                city="Kyoto",
                confidence_score=0.60,
                is_uncertain=True,
            )

            out_csv = Path(tmpdir) / "output.csv"
            engine = PhotoScraperEngine(gemini_parser=mock_parser, dry_run=True)

            with (
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="c"),
            ):
                rows = engine.scan_and_export(
                    photo_dir=photo_dir,
                    output_csv=out_csv,
                    non_interactive=False,
                )

                assert len(rows) == 1
                assert rows[0].name == "Airport Hotel"
                assert rows[0].triage_status == "APPROVED"

    def test_scan_and_export_interactive_edit(self) -> None:
        """Asserts interactive prompt [e] allows editing name and approves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            photo_dir = Path(tmpdir) / "photos"
            sub_dir = photo_dir / "2024" / "Kyoto"
            sub_dir.mkdir(parents=True)

            img_path = sub_dir / "IMG_303.JPG"
            Image.new("RGB", (10, 10)).save(img_path)

            mock_parser = MagicMock()
            mock_parser.is_configured.return_value = True
            mock_parser.infer_poi.return_value = PhotoPOIInference(
                name="Old Tea House",
                description="Historic house",
                confidence_score=0.50,
                is_uncertain=True,
            )

            out_csv = Path(tmpdir) / "output.csv"
            engine = PhotoScraperEngine(gemini_parser=mock_parser, dry_run=True)

            inputs = iter(["e", "Custom Tea Sanctuary", "Refined matcha house"])
            with (
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=lambda *args: next(inputs)),
            ):
                rows = engine.scan_and_export(
                    photo_dir=photo_dir,
                    output_csv=out_csv,
                    non_interactive=False,
                )

                assert len(rows) == 1
                assert rows[0].name == "Custom Tea Sanctuary"
                assert rows[0].description == "Refined matcha house"
                assert rows[0].triage_status == "APPROVED"

    def test_scan_and_export_interactive_skip(self) -> None:
        """Asserts interactive prompt [s] excludes the POI from export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            photo_dir = Path(tmpdir) / "photos"
            sub_dir = photo_dir / "2024" / "Kyoto"
            sub_dir.mkdir(parents=True)

            img_path = sub_dir / "IMG_404.JPG"
            Image.new("RGB", (10, 10)).save(img_path)

            mock_parser = MagicMock()
            mock_parser.is_configured.return_value = True
            mock_parser.infer_poi.return_value = PhotoPOIInference(
                name="Random Corner",
                description="Unknown place",
                confidence_score=0.40,
                is_uncertain=True,
            )

            out_csv = Path(tmpdir) / "output.csv"
            engine = PhotoScraperEngine(gemini_parser=mock_parser, dry_run=True)

            with (
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="s"),
            ):
                rows = engine.scan_and_export(
                    photo_dir=photo_dir,
                    output_csv=out_csv,
                    non_interactive=False,
                )

                assert len(rows) == 0
