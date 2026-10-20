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

"""End-to-end integration test for AI photo directory scanner CLI (T-040).

Verifies:
- Complete directory hierarchy scan across multi-folder tree
- Exclusion pattern filtering (*Raw*)
- EXIF GPS and timestamp extraction from real image files
- Gemini structured inference with fallback and uncertainty triage
- Output CSV generation conforming to canonical Vistarae ingestion schema
- Formula prefix neutralization in generated CSV output
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from photo_scraper.main import main


class TestScraperEndToEnd:
    """End-to-end integration test for photo scraper CLI."""

    def test_directory_scan_and_csv_generation(self) -> None:
        """Executes full CLI scan on a synthetic folder structure and verifies output CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            photos_root = base_dir / "Photos"

            # 1. Folder 1: Confident Landmark
            folder1 = photos_root / "2024" / "Japan" / "Kyoto" / "Fushimi_Inari"
            folder1.mkdir(parents=True)
            img1_path = folder1 / "IMG_001.JPG"
            img1 = Image.new("RGB", (20, 20), color=(255, 0, 0))
            exif1 = img1.getexif()
            exif1[36867] = "2024:04:10 09:30:00"
            gps1 = exif1.get_ifd(0x8825)
            gps1[1] = "N"
            gps1[2] = (34, 58, 1.56)  # ~34.9671 N
            gps1[3] = "E"
            gps1[4] = (135, 46, 21.72)  # ~135.7727 E
            img1.save(img1_path, exif=exif1)

            # 2. Folder 2: Generic / Uncertain dining location
            folder2 = photos_root / "2024" / "Japan" / "Kyoto" / "Dinner_Gion"
            folder2.mkdir(parents=True)
            img2_path = folder2 / "IMG_002.JPG"
            img2 = Image.new("RGB", (20, 20), color=(0, 255, 0))
            exif2 = img2.getexif()
            exif2[36867] = "2024:04:12 19:15:00"
            gps2 = exif2.get_ifd(0x8825)
            gps2[1] = "N"
            gps2[2] = (35, 0, 13.32)  # ~35.0037 N
            gps2[3] = "E"
            gps2[4] = (135, 46, 37.92)  # ~135.7772 E
            img2.save(img2_path, exif=exif2)

            # 3. Folder 3: Excluded raw directory
            folder3 = photos_root / "2024" / "Raw_Files" / "Backup"
            folder3.mkdir(parents=True)
            img3_path = folder3 / "RAW_001.JPG"
            Image.new("RGB", (20, 20)).save(img3_path)

            out_csv = base_dir / "ingest_result.csv"

            # Mock Gemini generate_content responses
            fushimi_resp = {
                "name": "Fushimi Inari Taisha",
                "description": "Historic shrine with torii gate paths.",
                "city": "Kyoto",
                "state": "Kyoto Prefecture",
                "country": "Japan",
                "confidence_score": 0.95,
                "is_uncertain": False,
            }
            gion_resp = {
                "name": "=Gion Traditional Restaurant",
                "description": "Dining establishment in historic district.",
                "city": "Kyoto",
                "state": "Kyoto Prefecture",
                "country": "Japan",
                "confidence_score": 0.55,
                "is_uncertain": True,
            }

            def mock_generate_content(*args, **kwargs):
                contents = kwargs.get("contents", "")
                mock_res = MagicMock()
                if "Fushimi_Inari" in str(contents):
                    mock_res.text = json.dumps(fushimi_resp)
                else:
                    mock_res.text = json.dumps(gion_resp)
                return mock_res

            mock_models = MagicMock()
            mock_models.generate_content.side_effect = mock_generate_content
            mock_client = MagicMock()
            mock_client.models = mock_models

            with patch("google.genai.Client", return_value=mock_client):
                # Execute CLI entrypoint
                cli_args = [
                    "--dir",
                    str(photos_root),
                    "--out",
                    str(out_csv),
                    "--non-interactive",
                    "--exclude",
                    "*Raw_Files*",
                ]
                main(cli_args)

            # Verify output CSV
            assert out_csv.exists()
            with open(out_csv, encoding="utf-8") as f:
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

                rows = list(reader)
                # Exactly 2 rows (folder3 was excluded)
                assert len(rows) == 2

                fushimi_row = next((r for r in rows if "Fushimi" in r[0]), None)
                gion_row = next((r for r in rows if "Gion" in r[0]), None)

                assert fushimi_row is not None
                assert fushimi_row[0] == "Fushimi Inari Taisha"
                assert fushimi_row[3] == "Kyoto"
                assert fushimi_row[5] == "Japan"
                assert round(float(fushimi_row[6]), 2) == 34.97
                assert round(float(fushimi_row[7]), 2) == 135.77
                assert fushimi_row[8] == "2024-04-10"
                assert fushimi_row[10] == "APPROVED"

                assert gion_row is not None
                assert gion_row[0] == "'=Gion Traditional Restaurant"
                assert gion_row[8] == "2024-04-12"
                assert gion_row[10] == "NEEDS_REVIEW"
