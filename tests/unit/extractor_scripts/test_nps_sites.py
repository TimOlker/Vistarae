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

"""Unit tests for NPSSitesExtractor using static HTML fixtures."""

from pathlib import Path

import httpx
from click.testing import CliRunner

from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractorConfig
from extractor_scripts.nps_sites import NPSSitesExtractor, cli

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_nps_sites_harvest() -> None:
    """Verifies parsing of park directory, baseline/conditional tags, and additional addresses."""
    html = (FIXTURES_DIR / "nps_directory.html").read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )

    config = ExtractorConfig(output_path=Path("nps.csv"))
    extractor = NPSSitesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 3

    # Check Yellowstone
    yell = records[0]
    assert yell.poi_name == "Yellowstone National Park"
    assert yell.country == "United States"
    assert yell.country_code == "US"
    assert yell.state_province == "WY"
    assert yell.town_city == "Mammoth"
    assert yell.street_address == "2 Officers Row"
    assert yell.zip_code == "82190"
    assert float(yell.latitude) == 44.4280
    assert float(yell.longitude) == -110.5885
    # Tag checks: baseline NPS + National Park
    assert "NPS" in yell.tags
    assert "National Park" in yell.tags
    # Website check
    assert len(yell.websites) == 1
    assert yell.websites[0].url == "https://www.nps.gov/yell/index.htm"
    # Additional addresses check
    assert len(yell.additional_addresses) == 2
    assert yell.additional_addresses[0].street_address == "Old Faithful Area"
    assert float(yell.additional_addresses[0].latitude) == 44.4590

    # Check Fort Laramie
    fols = records[1]
    assert fols.poi_name == "Fort Laramie National Historic Site"
    assert "NPS" in fols.tags
    assert "National Historic Site" in fols.tags
    assert len(fols.additional_addresses) == 0

    # Check Gettysburg
    gett = records[2]
    assert gett.poi_name == "Gettysburg National Military Park"
    assert "NPS" in gett.tags
    assert "National Military Park" in gett.tags


def test_nps_cli_dry_run(monkeypatch) -> None:
    """Verifies NPS CLI execution with --dry-run option."""
    html = (FIXTURES_DIR / "nps_directory.html").read_text(encoding="utf-8")

    def mock_get(self, url, **kwargs):
        return html

    monkeypatch.setattr(ResilientHttpClient, "get", mock_get)

    runner = CliRunner()
    result = runner.invoke(cli, ["--dry-run", "--limit", "2"])
    assert result.exit_code == 0
    assert "Vistarae Extractor Summary: NPSSites (DRY RUN)" in result.output
    assert "Total Records Harvested: 2" in result.output


def test_nps_sites_malformed_items() -> None:
    """Verifies skipping of malformed park items and invalid coordinate strings."""
    html = """
    <div class="park-list">
      <div class="park-item"></div>
      <div class="park-item"><h2></h2></div>
      <div class="park-item">
        <h2><a>Bad Coords Park</a></h2>
        <span class="lat">abc</span>
        <span class="lon">def</span>
        <div class="additional-locations">
          <div class="location" data-lat="x" data-lon="y">Loc 1</div>
        </div>
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
    extractor = NPSSitesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()
    assert len(records) == 1
    assert records[0].poi_name == "Bad Coords Park"
    assert records[0].latitude is None
    assert len(records[0].additional_addresses) == 1
    assert records[0].additional_addresses[0].latitude is None


def test_nps_sites_harvest_live_accordions() -> None:
    """Verifies parsing of the live official National Park System accordion layout."""
    html = """
    <div id="main">
      <h4 class="usa-accordion__heading">
        <button class="usa-accordion__button">National Battlefields (2)</button>
      </h4>
      <div class="usa-accordion__content">
        <p>
          <a href="https://www.nps.gov/anti/index.htm">Antietam National Battlefield</a>, Maryland<br/>
          <a href="https://www.nps.gov/fodo/index.htm">Fort Donelson National Battlefield</a>, Kentucky and Tennessee
        </p>
      </div>
      <h4 class="usa-accordion__heading">
        <button class="usa-accordion__button">National Parks (1)</button>
      </h4>
      <div class="usa-accordion__content">
        <p>
          <a href="https://www.nps.gov/acad/index.htm">Acadia National Park</a>, Maine
        </p>
      </div>
    </div>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(delay_seconds=0.0, cache_enabled=False, transport=transport)
    config = ExtractorConfig(output_path=Path("out.csv"), cache_enabled=False)
    extractor = NPSSitesExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 3

    # Check Antietam
    anti = records[0]
    assert anti.poi_name == "Antietam National Battlefield"
    assert anti.state_province == "MD"
    assert anti.country == "United States"
    assert anti.country_code == "US"
    assert "NPS" in anti.tags
    assert "National Battlefield" in anti.tags
    assert len(anti.websites) == 1
    assert anti.websites[0].url == "https://www.nps.gov/anti/index.htm"
    assert len(anti.additional_addresses) == 0

    # Check Fort Donelson with multi-state
    fodo = records[1]
    assert fodo.poi_name == "Fort Donelson National Battlefield"
    assert fodo.state_province == "KY"
    assert len(fodo.additional_addresses) == 1
    assert fodo.additional_addresses[0].state_province == "TN"
    assert fodo.additional_addresses[0].country == "United States"
    assert fodo.additional_addresses[0].country_code == "US"

    # Check Acadia
    acad = records[2]
    assert acad.poi_name == "Acadia National Park"
    assert acad.state_province == "ME"
    assert "National Park" in acad.tags
