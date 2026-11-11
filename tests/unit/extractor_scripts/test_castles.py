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

"""Unit tests for CastlesExtractor using static HTML fixtures."""

from pathlib import Path

import httpx
from click.testing import CliRunner

from extractor_scripts.castles import CastlesExtractor, cli
from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractorConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_castles_harvest() -> None:
    """Verifies castle parsing, Fortification baseline tag, omission of architecture tags, and hero images."""
    html = (FIXTURES_DIR / "castles_selection.html").read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )

    config = ExtractorConfig(output_path=Path("castles.csv"))
    extractor = CastlesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 3

    # Neuschwanstein Castle
    neuschwanstein = records[0]
    assert neuschwanstein.poi_name == "Neuschwanstein Castle"
    assert neuschwanstein.country == "Germany"
    assert neuschwanstein.country_code == "DE"
    assert neuschwanstein.state_province == "Bavaria"
    assert neuschwanstein.town_city == "Schwangau"
    assert float(neuschwanstein.latitude) == 47.5576
    assert float(neuschwanstein.longitude) == 10.7498
    assert (
        neuschwanstein.hero_image_url == "https://www.castlesworld.com/img/neuschwanstein_hero.jpg"
    )
    # Tag verification: Fortification ONLY, no architectural classifications
    assert neuschwanstein.tags == ["Fortification"]
    assert "Romanesque Revival" not in neuschwanstein.tags
    assert "Palace" not in neuschwanstein.tags
    # Website verification
    assert len(neuschwanstein.websites) == 1
    assert "neuschwanstein.html" in neuschwanstein.websites[0].url

    # Edinburgh Castle
    edinburgh = records[1]
    assert edinburgh.poi_name == "Edinburgh Castle"
    assert edinburgh.country == "United Kingdom"
    assert edinburgh.state_province == "Scotland"
    assert edinburgh.town_city == "Edinburgh"
    assert edinburgh.tags == ["Fortification"]

    # Chillon Castle
    chillon = records[2]
    assert chillon.poi_name == "Chillon Castle"
    assert chillon.country == "Switzerland"
    assert chillon.country_code == "CH"
    assert chillon.state_province == "Vaud"
    assert chillon.town_city == "Montreux"
    assert chillon.tags == ["Fortification"]
    assert "Medieval" not in chillon.tags


def test_castles_cli_dry_run(monkeypatch) -> None:
    """Verifies Castles CLI execution with --dry-run option."""
    html = (FIXTURES_DIR / "castles_selection.html").read_text(encoding="utf-8")

    def mock_get(self, url, **kwargs):
        return html

    monkeypatch.setattr(ResilientHttpClient, "get", mock_get)

    runner = CliRunner()
    result = runner.invoke(cli, ["--dry-run", "--limit", "2"])
    assert result.exit_code == 0
    assert "Vistarae Extractor Summary: Castles (DRY RUN)" in result.output
    assert "Total Records Harvested: 2" in result.output


def test_castles_malformed_cards() -> None:
    """Verifies graceful handling of malformed castle cards and invalid coordinates."""
    html = """
    <div>
      <div class="castle-card"></div>
      <div class="castle-card"><h3></h3></div>
      <div class="castle-card">
        <h3><a>Test Castle</a></h3>
        <span class="coords" data-lat="not-a-float" data-lon="bad"></span>
      </div>
    </div>
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
    extractor = CastlesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()
    assert len(records) == 1
    assert records[0].poi_name == "Test Castle"
    assert records[0].latitude is None


def test_castles_harvest_live_table() -> None:
    """Verifies parsing of the live Castles World selection table layout."""
    html = """
    <table>
      <tr>
        <td><a class="castlename" href="https://www.castlesworld.com/castles/castle-of-hierges.php">Castle of Hierges</a></td>
        <td>France</td>
        <td>Hierges, Ardennes department</td>
        <td>★★★★☆</td>
      </tr>
      <tr>
        <td><a class="castlename" href="https://www.castlesworld.com/castles/castle-of-sedan.php">Castle of Sedan</a></td>
        <td>France</td>
        <td>Sedan</td>
        <td>★★★★★</td>
      </tr>
    </table>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(delay_seconds=0.0, cache_enabled=False, transport=transport)
    config = ExtractorConfig(output_path=Path("castles.csv"), cache_enabled=False)
    extractor = CastlesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 2

    # Check Hierges
    hierges = records[0]
    assert hierges.poi_name == "Castle of Hierges"
    assert hierges.country == "France"
    assert hierges.country_code == "FR"
    assert hierges.town_city == "Hierges"
    assert hierges.state_province == "Ardennes department"
    assert hierges.tags == ["Fortification"]
    assert len(hierges.websites) == 1
    assert "castle-of-hierges.php" in hierges.websites[0].url

    # Check Sedan
    sedan = records[1]
    assert sedan.poi_name == "Castle of Sedan"
    assert sedan.country == "France"
    assert sedan.town_city == "Sedan"
    assert sedan.state_province is None


def test_castles_harvest_table_edge_cases() -> None:
    """Verifies edge cases in Castles World table parsing."""
    html = """
    <table>
      <tr>
        <td>No castle link here</td>
      </tr>
      <tr>
        <td><a class="castlename" href=""></a></td>
      </tr>
      <tr>
        <td><a class="castlename" href="#">Castle Solo</a></td>
      </tr>
    </table>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(delay_seconds=0.0, cache_enabled=False, transport=transport)
    config = ExtractorConfig(output_path=Path("castles.csv"), cache_enabled=False)
    extractor = CastlesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 1
    assert records[0].poi_name == "Castle Solo"
    assert records[0].country == "Unknown"
    assert records[0].town_city is None
    assert len(records[0].websites) == 0
