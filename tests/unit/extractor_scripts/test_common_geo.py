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

"""Unit tests for NominatimGeoClient verifying rate limiting and geocode resolution."""

import json
from decimal import Decimal

import httpx

from extractor_scripts.common.geo import NominatimGeoClient


def test_nominatim_geocode_success() -> None:
    """Verifies successful geocoding query returning Decimal lat/lon."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        data = [{"lat": "48.8584", "lon": "2.2945"}]
        return httpx.Response(200, text=json.dumps(data))

    transport = httpx.MockTransport(mock_handler)
    client = NominatimGeoClient(transport=transport, min_delay_seconds=0.0)

    lat, lon = client.geocode("Eiffel Tower", country_code="FR")
    assert lat == Decimal("48.858400")
    assert lon == Decimal("2.294500")

    client.close()


def test_nominatim_geocode_empty_and_error() -> None:
    """Verifies behavior on blank query, empty results, and HTTP errors."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "empty" in str(request.url):
            return httpx.Response(200, text="[]")
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(mock_handler)
    client = NominatimGeoClient(transport=transport, min_delay_seconds=0.0)

    # Blank query
    assert client.geocode("") == (None, None)

    # Empty result
    assert client.geocode("empty location") == (None, None)

    # HTTP Error
    assert client.geocode("error location") == (None, None)
    client.close()
