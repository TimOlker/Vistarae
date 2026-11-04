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

"""Unit tests for AircraftMuseumsExtractor using static HTML fixtures."""

from pathlib import Path

import httpx
from click.testing import CliRunner

from extractor_scripts.aircraft_museums import AircraftMuseumsExtractor, cli
from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractorConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_aircraft_museums_harvest() -> None:
    """Verifies aircraft museum parsing, Aircraft baseline tag, omission of collection focus tags, and JSON links."""
    html = (FIXTURES_DIR / "aviation_museums_wiki.html").read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )

    config = ExtractorConfig(output_path=Path("aircraft.csv"))
    extractor = AircraftMuseumsExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 3

    # National Air and Space Museum
    nasm = records[0]
    assert nasm.poi_name == "National Air and Space Museum"
    assert nasm.country == "United States"
    assert nasm.country_code == "US"
    assert nasm.state_province == "District of Columbia"
    assert nasm.town_city == "Washington, D.C."
    assert float(nasm.latitude) == 38.8882
    assert float(nasm.longitude) == -77.0199
    # Tags: Aircraft ONLY (no collection focus tags like Space or Military)
    assert nasm.tags == ["Aircraft"]
    assert "Space" not in nasm.tags
    assert "Military" not in nasm.tags
    # Websites: Wikipedia + Smithsonian
    assert len(nasm.websites) == 2
    assert "airandspace.si.edu" in nasm.websites[1].url

    # Imperial War Museum Duxford
    duxford = records[1]
    assert duxford.poi_name == "Imperial War Museum Duxford"
    assert duxford.country == "United Kingdom"
    assert duxford.country_code == "GB"
    assert duxford.state_province == "Cambridgeshire"
    assert duxford.town_city == "Duxford Airfield"
    assert duxford.tags == ["Aircraft"]
    assert "Warbirds" not in duxford.tags

    # Musée de l'air et de l'espace
    paris = records[2]
    assert paris.poi_name == "Musée de l'air et de l'espace"
    assert paris.country == "France"
    assert paris.country_code == "FR"
    assert paris.town_city == "Le Bourget Airport"
    assert paris.tags == ["Aircraft"]


def test_aircraft_museums_cli_dry_run(monkeypatch) -> None:
    """Verifies Aircraft Museums CLI execution with --dry-run option."""
    html = (FIXTURES_DIR / "aviation_museums_wiki.html").read_text(encoding="utf-8")

    def mock_get(self, url, **kwargs):
        return html

    monkeypatch.setattr(ResilientHttpClient, "get", mock_get)

    runner = CliRunner()
    result = runner.invoke(cli, ["--dry-run", "--limit", "2"])
    assert result.exit_code == 0
    assert "Vistarae Extractor Summary: AircraftMuseums (DRY RUN)" in result.output
    assert "Total Records Harvested: 2" in result.output


def test_aircraft_museums_malformed_rows() -> None:
    """Verifies graceful skipping of short or invalid DOM elements."""
    html = "<table><tr><td>Header</td></tr><tr><td></td></tr></table>"

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )
    config = ExtractorConfig(output_path=Path("out.csv"), cache_enabled=False)
    extractor = AircraftMuseumsExtractor(config=config, http_client=http_client)
    assert extractor.harvest_records() == []
    # Test invalid coordinate parsing directly
    assert extractor._parse_coordinates("invalid coords") == (None, None)


def test_aircraft_museums_harvest_wiki_sections() -> None:
    """Verifies parsing of the live Wikipedia section/list layout."""
    html = """
    <div class="mw-parser-output">
      <section>
        <div class="mw-heading mw-heading2"><h2>France</h2></div>
        <ul>
          <li><a href="/wiki/Aeroscopia">Aeroscopia</a>, Blagnac</li>
        </ul>
      </section>
      <section>
        <div class="mw-heading mw-heading2"><h2>United States</h2></div>
        <section>
          <div class="mw-heading mw-heading3"><h3>Alabama</h3></div>
          <ul>
            <li><a href="/wiki/Southern_Museum_of_Flight">Southern Museum of Flight</a>, Birmingham</li>
          </ul>
        </section>
      </section>
      <section>
        <div class="mw-heading mw-heading2"><h2>References</h2></div>
      </section>
    </div>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(delay_seconds=0.0, cache_enabled=False, transport=transport)
    config = ExtractorConfig(output_path=Path("aircraft.csv"), cache_enabled=False)
    extractor = AircraftMuseumsExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 2

    # Check French museum
    aero = records[0]
    assert aero.poi_name == "Aeroscopia"
    assert aero.country == "France"
    assert aero.country_code == "FR"
    assert aero.town_city == "Blagnac"
    assert aero.tags == ["Aircraft"]
    assert len(aero.websites) == 1
    assert "Aeroscopia" in aero.websites[0].url

    # Check US museum with state subdivision
    flight = records[1]
    assert flight.poi_name == "Southern Museum of Flight"
    assert flight.country == "United States"
    assert flight.country_code == "US"
    assert flight.state_province == "Alabama"
    assert flight.town_city == "Birmingham"
    assert flight.tags == ["Aircraft"]


def test_aircraft_museums_wiki_sections_edge_cases() -> None:
    """Verifies edge cases in Wikipedia section harvesting and list parsing."""
    html = """
    <div class="mw-parser-output">
      <section>
        <!-- No h2 -->
        <ul><li>Item without section h2</li></ul>
      </section>
      <section>
        <h2>See also</h2>
        <ul><li>Ignored</li></ul>
      </section>
      <section>
        <h2>Canada</h2>
        <ul>
          <li>Plain text no link</li>
          <li><a href="/wiki/Category:Airports">Category:Airports</a></li>
          <li><a href="/wiki/List_of_airports">List of airports</a></li>
          <li><a href="#Internal">Local Museum</a> - Somewhere</li>
        </ul>
      </section>
      <table>
        <tr><td>Not enough cells</td></tr>
      </table>
    </div>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(delay_seconds=0.0, cache_enabled=False, transport=transport)
    config = ExtractorConfig(output_path=Path("aircraft.csv"), cache_enabled=False)
    extractor = AircraftMuseumsExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 1
    assert records[0].poi_name == "Local Museum"
    assert records[0].country == "Canada"
    assert records[0].country_code == "CA"
    # Local # href should not produce a website
    assert len(records[0].websites) == 0
