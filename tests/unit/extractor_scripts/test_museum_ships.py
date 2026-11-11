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

"""Unit tests for MuseumShipsExtractor using static HTML fixtures."""

from pathlib import Path

import httpx
from click.testing import CliRunner

from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractorConfig
from extractor_scripts.museum_ships import MuseumShipsExtractor, cli

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_museum_ships_harvest() -> None:
    """Verifies vessel parsing, baseline Ship tag, conditional Military tag, and omission of naval types."""
    html = (FIXTURES_DIR / "museum_ships_wiki.html").read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )

    config = ExtractorConfig(output_path=Path("ships.csv"))
    extractor = MuseumShipsExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 4

    # USS Intrepid (Aircraft carrier / Warship)
    intrepid = records[0]
    assert intrepid.poi_name == "USS Intrepid (CV-11)"
    assert intrepid.country == "United States"
    assert intrepid.country_code == "US"
    assert intrepid.town_city == "New York City"
    assert intrepid.state_province == "NY"
    assert float(intrepid.latitude) == 40.7645
    assert float(intrepid.longitude) == -73.9996
    # Tags: Ship and Military, but NO naval classifications
    assert "Ship" in intrepid.tags
    assert "Military" in intrepid.tags
    assert "Aircraft carrier" not in intrepid.tags
    assert "Warship" not in intrepid.tags
    # Websites: Wikipedia + Museum link
    assert len(intrepid.websites) == 2
    assert "intrepidmuseum.org" in intrepid.websites[1].url

    # HMS Belfast (Light cruiser / Warship)
    belfast = records[1]
    assert belfast.poi_name == "HMS Belfast"
    assert belfast.country == "United Kingdom"
    assert "Ship" in belfast.tags
    assert "Military" in belfast.tags
    assert "Light cruiser" not in belfast.tags

    # USS Nautilus (Submarine / Warship)
    nautilus = records[2]
    assert nautilus.poi_name == "USS Nautilus (SSN-571)"
    assert "Ship" in nautilus.tags
    assert "Military" in nautilus.tags
    assert "Submarine" not in nautilus.tags

    # Cutty Sark (Civilian merchant)
    cutty = records[3]
    assert cutty.poi_name == "Cutty Sark"
    assert cutty.country == "United Kingdom"
    assert "Ship" in cutty.tags
    assert "Military" not in cutty.tags
    assert "Clipper" not in cutty.tags


def test_museum_ships_cli_dry_run(monkeypatch) -> None:
    """Verifies CLI execution with --dry-run option."""
    html = (FIXTURES_DIR / "museum_ships_wiki.html").read_text(encoding="utf-8")

    def mock_get(self, url, **kwargs):
        return html

    monkeypatch.setattr(ResilientHttpClient, "get", mock_get)

    runner = CliRunner()
    result = runner.invoke(cli, ["--dry-run", "--limit", "2"])
    assert result.exit_code == 0
    assert "Vistarae Extractor Summary: MuseumShips (DRY RUN)" in result.output
    assert "Total Records Harvested: 2" in result.output


def test_museum_ships_malformed_rows() -> None:
    """Verifies malformed rows skipping and coordinates parse error fallback."""
    html = """
    <table>
      <tr><td>Ship Name</td></tr>
      <tr><td>1</td><td>Type</td></tr>
      <tr><td></td><td>Type</td><td>US</td><td>Port</td></tr>
    </table>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )
    config = ExtractorConfig(output_path=Path("out.csv"), cache_enabled=False)
    extractor = MuseumShipsExtractor(config=config, http_client=http_client)
    assert extractor.harvest_records() == []
    assert extractor._parse_coordinates("bad lat lon") == (None, None)
