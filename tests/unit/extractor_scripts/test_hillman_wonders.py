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

"""Unit tests for HillmanWondersExtractor using static HTML fixtures."""

from pathlib import Path

import httpx
from click.testing import CliRunner

from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractorConfig
from extractor_scripts.hillman_wonders import (
    HillmanWondersExtractor,
    cli,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_hillman_wonders_harvest_shallow() -> None:
    """Verifies shallow parsing of index table, rank tiers, and JSON websites."""
    index_html = (FIXTURES_DIR / "hillman_index.html").read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=index_html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )

    config = ExtractorConfig(
        output_path=Path("out.csv"),
        deep_scrape=False,
    )
    extractor = HillmanWondersExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 5

    # Check first record (Gold)
    rec_0 = records[0]
    assert rec_0.poi_name == "Pyramids of Giza"
    assert rec_0.country == "Egypt"
    assert rec_0.country_code == "EG"
    assert "HillmanWonder:Gold" in rec_0.tags
    assert "Wonder" not in rec_0.tags
    assert len(rec_0.websites) == 1
    assert rec_0.websites[0].name == "Hillman Wonders"
    assert "giza_pyramids.htm" in rec_0.websites[0].url
    assert rec_0.description is None
    assert rec_0.reason_to_visit is None

    # Check silver record
    rec_silver = next(r for r in records if r.poi_name == "Acropolis of Athens")
    assert rec_silver.country == "Greece"
    assert "HillmanWonder:Silver" in rec_silver.tags
    assert "Wonder" not in rec_silver.tags

    # Check bronze record
    rec_bronze = next(r for r in records if r.poi_name == "Neuschwanstein Castle")
    assert rec_bronze.country == "Germany"
    assert "HillmanWonder:Bronze" in rec_bronze.tags
    assert "Wonder" not in rec_bronze.tags


def test_hillman_wonders_harvest_deep() -> None:
    """Verifies deep parsing fetching subpage details (hero image, coordinates)."""
    index_html = (FIXTURES_DIR / "hillman_index.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "hillman_detail.html").read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "giza_pyramids.htm" in str(request.url):
            return httpx.Response(200, text=detail_html)
        return httpx.Response(200, text=index_html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )

    config = ExtractorConfig(
        output_path=Path("out.csv"),
        limit=1,
        deep_scrape=True,
    )
    extractor = HillmanWondersExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 1
    rec = records[0]
    assert rec.poi_name == "Pyramids of Giza"
    assert rec.hero_image_url == "https://www.hillmanwonders.com/photos/pyramids_hero.jpg"
    assert float(rec.latitude) == 29.9792
    assert float(rec.longitude) == 31.1342
    assert rec.description is None
    assert rec.reason_to_visit is None


def test_hillman_cli_dry_run(monkeypatch) -> None:
    """Verifies CLI execution with --dry-run option."""
    index_html = (FIXTURES_DIR / "hillman_index.html").read_text(encoding="utf-8")

    def mock_get(self, url, **kwargs):
        return index_html

    monkeypatch.setattr(ResilientHttpClient, "get", mock_get)

    runner = CliRunner()
    result = runner.invoke(cli, ["--dry-run", "--limit", "2"])
    assert result.exit_code == 0
    assert "Vistarae Extractor Summary: HillmanWonders (DRY RUN)" in result.output
    assert "Total Records Harvested: 2" in result.output


def test_hillman_wonders_malformed_rows_and_deep_errors() -> None:
    """Verifies malformed rows skipping and subpage network error tolerance."""
    html = """
    <table>
      <tr><td>Header</td></tr>
      <tr><td>1</td><td><a></a></td><td>Egypt</td></tr>
      <tr><td>2</td><td><a href="broken.htm">Broken Wonder</a></td><td>Egypt</td><td>Gold</td></tr>
    </table>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "broken.htm" in str(request.url):
            return httpx.Response(500, text="Server Error")
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        transport=transport,
    )
    config = ExtractorConfig(
        output_path=Path("out.csv"),
        deep_scrape=True,
        cache_enabled=False,
    )
    extractor = HillmanWondersExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()
    assert len(records) == 1
    assert records[0].poi_name == "Broken Wonder"


def test_hillman_wonders_country_directory_layout() -> None:
    """Verifies parsing of the real-world country-grouped directory layout."""
    html = """
    <table>
      <tr>
        <td class="CountryName">Afghanistan</td>
        <td class="WonderList">
          <img src="b_bronze.gif"/>Jam Minaret<br/>
          <img src="b_gold.gif"/>Kabul Old City<br/>
          <img src="b_silver.gif"/>Khyber Pass<span style="font-weight:normal;">&nbsp;[with Pakistan]</span>
          <td class="LinkCellText">to see my Top 10 rankings</td>
        </td>
      </tr>
      <tr>
        <td class="CountryName">America</td>
        <td class="WonderList">
          <img src="b_gold.gif"/>Grand Canyon<br/>
        </td>
      </tr>
      <tr>
        <td class="CountryName">Covered in other lists</td>
        <td class="WonderList"></td>
      </tr>
    </table>
    """

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    http_client = ResilientHttpClient(delay_seconds=0.0, cache_enabled=False, transport=transport)
    config = ExtractorConfig(output_path=Path("out.csv"), cache_enabled=False)
    extractor = HillmanWondersExtractor(config=config, http_client=http_client)
    records = extractor.harvest_records()

    assert len(records) == 4
    # Check bronze
    assert records[0].poi_name == "Jam Minaret"
    assert records[0].country == "Afghanistan"
    assert records[0].country_code == "AF"
    assert records[0].tags == ["HillmanWonder:Bronze"]
    # Verify no source list website populated
    assert len(records[0].websites) == 0
    assert records[0].description is None

    # Check gold
    assert records[1].poi_name == "Kabul Old City"
    assert records[1].tags == ["HillmanWonder:Gold"]

    # Check silver
    assert "Khyber Pass" in records[2].poi_name
    assert records[2].tags == ["HillmanWonder:Silver"]

    # Check America normalization to United States
    assert records[3].poi_name == "Grand Canyon"
    assert records[3].country == "United States"
    assert records[3].country_code == "US"
    assert records[3].tags == ["HillmanWonder:Gold"]
