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

"""Unit tests for UrlCoordinateExtractor and URL coordinate parsing helpers."""

from __future__ import annotations

import pytest

from services.poi.services.url_extractor import (
    UrlCoordinateExtractor,
    clean_url,
    extract_tripadvisor_slug,
    parse_dms_string,
    parse_geohack_params,
    parse_geohack_url,
    parse_google_maps_url_py,
    parse_unesco_html,
)


def test_clean_url_removes_text_fragments() -> None:
    url = "https://en.wikipedia.org/wiki/Shibaozhai#:~:text=At%20the%20top%20of%20Shibaozhai"
    assert clean_url(url) == "https://en.wikipedia.org/wiki/Shibaozhai"

    plain = "https://example.com/place"
    assert clean_url(plain) == "https://example.com/place"


def test_parse_geohack_params_decimal() -> None:
    # 30.42188_N_108.18389_E
    coords = parse_geohack_params("30.42187999245106_N_108.18389453817412_E_region:CN-CQ_type:landmark")
    assert coords is not None
    lat, lng = coords
    assert pytest.approx(lat, rel=1e-5) == 30.42188
    assert pytest.approx(lng, rel=1e-5) == 108.18389


def test_parse_geohack_params_dms() -> None:
    # 51_30_02_N_0_07_29_W
    coords = parse_geohack_params("51_30_02_N_0_07_29_W")
    assert coords is not None
    lat, lng = coords
    assert pytest.approx(lat, abs=0.01) == 51.5005
    assert pytest.approx(lng, abs=0.01) == -0.1247


def test_parse_geohack_params_semicolon() -> None:
    coords = parse_geohack_params("35.6895;139.6917")
    assert coords is not None
    lat, lng = coords
    assert pytest.approx(lat, rel=1e-4) == 35.6895
    assert pytest.approx(lng, rel=1e-4) == 139.6917


def test_parse_geohack_url() -> None:
    url = "https://geohack.toolforge.org/geohack.php?pagename=Shibaozhai&params=30.42187999245106_N_108.18389453817412_E_region:CN-CQ"
    res = parse_geohack_url(url)
    assert res is not None
    lat, lng, name = res
    assert pytest.approx(lat, rel=1e-5) == 30.42188
    assert pytest.approx(lng, rel=1e-5) == 108.18389
    assert name == "Shibaozhai"


def test_parse_google_maps_url_py() -> None:
    url = "https://www.google.com/maps/place/M'Zab/@32.4756753,3.7051475,5338m/data=!3m1!1e3!4m6!3m5!1s0x12642629edfa882d:0x21a37c0afb90d5fb!8m2!3d32.4727002!4d3.7082024!16s%2Fg%2F11ckr9rrns"
    res = parse_google_maps_url_py(url)
    assert res is not None
    lat, lng, name = res
    # Priority is given to exact pin !3d/!4d
    assert pytest.approx(lat, rel=1e-5) == 32.4727002
    assert pytest.approx(lng, rel=1e-5) == 3.7082024
    assert name == "M'Zab"


def test_extract_tripadvisor_slug() -> None:
    url = "https://www.tripadvisor.com/Attraction_Review-g1487177-d552670-Reviews-Shi_Bao_Zhai-Zhong_County.html"
    name = extract_tripadvisor_slug(url)
    assert name == "Shi Bao Zhai, Zhong County"


def test_url_extractor_direct_geohack() -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from services.poi.services.geocode_service import ReverseGeocodeService

    mock_reverse = MagicMock(spec=ReverseGeocodeService)
    mock_reverse.reverse_geocode = AsyncMock(
        return_value=MagicMock(
            place_name="Shibaozhai Fortress",
            street="Zhong County Rd",
            city="Chongqing",
            state_province="Chongqing",
            country="China",
            postal_code="404300",
            country_code="cn",
        )
    )

    extractor = UrlCoordinateExtractor(reverse_geocode_service=mock_reverse)
    res = asyncio.run(
        extractor.extract_coordinates_from_url(
            "https://geohack.toolforge.org/geohack.php?pagename=Shibaozhai&params=30.42187999245106_N_108.18389453817412_E"
        )
    )

    assert res.latitude is not None and pytest.approx(res.latitude, rel=1e-4) == 30.42188
    assert res.longitude is not None and pytest.approx(res.longitude, rel=1e-4) == 108.18389
    assert res.extraction_source == "geohack_url"
    assert res.city == "Chongqing"
    assert res.country == "China"


def test_url_extractor_html_microformat() -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    from services.poi.services.geocode_service import ReverseGeocodeService

    mock_reverse = MagicMock(spec=ReverseGeocodeService)
    mock_reverse.reverse_geocode = AsyncMock(
        return_value=MagicMock(
            place_name="London Eye",
            street="Riverside Building",
            city="London",
            state_province="England",
            country="United Kingdom",
            postal_code="SE1 7PB",
            country_code="gb",
        )
    )

    html_content = """
    <html>
      <head><title>London Eye - Attractions</title></head>
      <body>
        <h1>The London Eye</h1>
        <div class="geo"><span class="latitude">51.5033</span>; <span class="longitude">-0.1195</span></div>
      </body>
    </html>
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content
    mock_client.get = AsyncMock(return_value=mock_resp)

    extractor = UrlCoordinateExtractor(
        reverse_geocode_service=mock_reverse,
        http_client=mock_client,
    )
    res = asyncio.run(extractor.extract_coordinates_from_url("https://example.com/attraction/london-eye"))

    assert res.latitude is not None and pytest.approx(res.latitude, rel=1e-4) == 51.5033
    assert res.longitude is not None and pytest.approx(res.longitude, rel=1e-4) == -0.1195
    assert res.extraction_source == "microformat_geo"
    assert res.city == "London"


def test_parse_dms_string_unesco_formats() -> None:
    """Verifies that various DMS/DM formats found on UNESCO and web pages parse accurately."""
    # User example: N16 01 06 E44 48 16 (Barāqish, Yemen)
    coords = parse_dms_string("N16 01 06 E44 48 16")
    assert coords is not None
    lat, lng = coords
    assert pytest.approx(lat, abs=0.0001) == 16.01833
    assert pytest.approx(lng, abs=0.0001) == 44.80444

    # With prefix
    c_pref = parse_dms_string("Coordinates: N16 01 06 E44 48 16")
    assert c_pref is not None
    assert pytest.approx(c_pref[0], abs=0.0001) == 16.01833
    assert pytest.approx(c_pref[1], abs=0.0001) == 44.80444

    # Southern & Western hemispheres with decimal seconds comma
    c_sw = parse_dms_string("S07 19 30,2 W35 35 6,8")
    assert c_sw is not None
    assert pytest.approx(c_sw[0], abs=0.0001) == -7.32505
    assert pytest.approx(c_sw[1], abs=0.0001) == -35.58522

    # High precision decimal seconds
    c_dec = parse_dms_string("S13 14 25.27 W159 48 50.65")
    assert c_dec is not None
    assert pytest.approx(c_dec[0], abs=0.0001) == -13.24035
    assert pytest.approx(c_dec[1], abs=0.0001) == -159.81407

    # Degrees and minutes only (no seconds)
    c_dm = parse_dms_string("N29 26 E48 20")
    assert c_dm is not None
    assert pytest.approx(c_dm[0], abs=0.0001) == 29.43333
    assert pytest.approx(c_dm[1], abs=0.0001) == 48.33333

    # Symbols: degree, minute, second
    c_sym = parse_dms_string("16°01'06\"N 44°48'16\"E")
    assert c_sym is not None
    assert pytest.approx(c_sym[0], abs=0.0001) == 16.01833
    assert pytest.approx(c_sym[1], abs=0.0001) == 44.80444

    # Trailing directions with commas
    c_trail = parse_dms_string("16 01 06 N, 44 48 16 E")
    assert c_trail is not None
    assert pytest.approx(c_trail[0], abs=0.0001) == 16.01833
    assert pytest.approx(c_trail[1], abs=0.0001) == 44.80444


def test_parse_unesco_html() -> None:
    """Verifies that UNESCO tentative list HTML is parsed for coordinates, site title, state, and country."""
    html = """
    <html>
      <head>
        <title>Barāqish City Archaeological Site  - UNESCO World Heritage Centre</title>
      </head>
      <body>
        <h1>Barāqish City Archaeological Site </h1>
        <div class="card">
          <div class="mb-2"><strong>State, Province or Region:</strong><br />Ma’rib Governorate</div>
          <div class="mb-2"><strong>Coordinates: </strong> N16 01 06 E44 48 16</div>
          <div class="mb-2"><strong>Submitted by:</strong><br />Permanent Delegation of the Republic of Yemen to UNESCO</div>
        </div>
        <div>
          <h4>Description</h4>
          <div>Geographically, Barāqish (Yathill) is located in Wādī al-Jawf, approximately 15 km south of the city of al-Ḥazm.</div>
        </div>
      </body>
    </html>
    """
    res = parse_unesco_html(html, "https://whc.unesco.org/en/tentativelists/6873/")
    assert res is not None
    assert "coordinates" in res
    lat, lng = res["coordinates"]
    assert pytest.approx(lat, abs=0.0001) == 16.01833
    assert pytest.approx(lng, abs=0.0001) == 44.80444
    assert res.get("name") == "Barāqish City Archaeological Site"
    assert res.get("state_province") == "Ma’rib Governorate"
    assert res.get("country") == "Yemen"
    assert "Geographically, Barāqish" in res.get("description", "")


def test_url_extractor_unesco_tentative_list_page() -> None:
    """Verifies that UrlCoordinateExtractor extracts coordinates and location from a UNESCO tentative list URL."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    from services.poi.services.geocode_service import ReverseGeocodeService

    mock_reverse = MagicMock(spec=ReverseGeocodeService)
    mock_reverse.reverse_geocode = AsyncMock(
        return_value=MagicMock(
            place_name="Barāqish",
            street=None,
            city="al-Ḥazm",
            state_province="Ma’rib Governorate",
            country="Yemen",
            postal_code=None,
            country_code="ye",
        )
    )

    unesco_html = """
    <html>
      <head>
        <title>Barāqish City Archaeological Site  - UNESCO World Heritage Centre</title>
      </head>
      <body>
        <h1>Barāqish City Archaeological Site </h1>
        <div class="card">
          <div class="mb-2"><strong>State, Province or Region:</strong><br />Ma’rib Governorate</div>
          <div class="mb-2"><strong>Coordinates: </strong> N16 01 06 E44 48 16</div>
          <div class="mb-2"><strong>Submitted by:</strong><br />Permanent Delegation of the Republic of Yemen to UNESCO</div>
        </div>
      </body>
    </html>
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = unesco_html
    mock_client.get = AsyncMock(return_value=mock_resp)

    extractor = UrlCoordinateExtractor(
        reverse_geocode_service=mock_reverse,
        http_client=mock_client,
    )
    res = asyncio.run(extractor.extract_coordinates_from_url("https://whc.unesco.org/en/tentativelists/6873/"))

    assert res.latitude is not None and pytest.approx(res.latitude, abs=0.0001) == 16.01833
    assert res.longitude is not None and pytest.approx(res.longitude, abs=0.0001) == 44.80444
    assert res.place_name == "Barāqish City Archaeological Site"
    assert res.extraction_source == "unesco_url"
    assert res.state_province == "Ma’rib Governorate"
    assert res.country == "Yemen"


def test_unesco_adapter_augment() -> None:
    """Verifies that UNESCOAdapter extracts coordinates and metadata from UNESCO URL."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    from services.poi.scraping.secondary_sources import UNESCOAdapter

    unesco_html = """
    <html>
      <head>
        <title>Barāqish City Archaeological Site  - UNESCO World Heritage Centre</title>
      </head>
      <body>
        <h1>Barāqish City Archaeological Site </h1>
        <div class="card">
          <div class="mb-2"><strong>State, Province or Region:</strong><br />Ma’rib Governorate</div>
          <div class="mb-2"><strong>Coordinates: </strong> N16 01 06 E44 48 16</div>
          <div class="mb-2"><strong>Submitted by:</strong><br />Permanent Delegation of the Republic of Yemen to UNESCO</div>
        </div>
        <div>
          <h4>Description</h4>
          <div>Geographically, Barāqish (Yathill) is located in Wādī al-Jawf...</div>
        </div>
      </body>
    </html>
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = unesco_html
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = UNESCOAdapter()
    data = asyncio.run(
        adapter.augment(
            source_url="https://whc.unesco.org/en/tentativelists/6873/",
            client=mock_client,
        )
    )

    assert data is not None
    assert data.get("source_name") == "unesco.org"
    assert data.get("site_name") == "Barāqish City Archaeological Site"
    assert data.get("latitude") is not None and pytest.approx(data["latitude"], abs=0.0001) == 16.01833
    assert data.get("longitude") is not None and pytest.approx(data["longitude"], abs=0.0001) == 44.80444
    assert data.get("state_province") == "Ma’rib Governorate"
    assert data.get("country") == "Yemen"
    assert "Geographically, Barāqish" in data.get("description", "")



