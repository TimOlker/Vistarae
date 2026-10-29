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

"""Unit tests for ambiguity penalty scoring in photo scraper (T-021).

Validates:
- Generic activities (Sledding, Picnic) without GPS receive score <= 15 (REQ-SCR-032)
- Multi-location commercial brands (McDonalds, Starbucks) without GPS receive score <= 30 (REQ-SCR-033)
- Valid coordinates preserve normal high confidence
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from services.scraper.cache import ScraperCacheManager
from services.scraper.location_resolver import (
    LocationResolver,
    check_ambiguity_penalty,
)
from services.scraper.path_parser import ParsedPathContext


def test_check_ambiguity_penalty_generic() -> None:
    """Verifies generic activity labels return penalty score <= 15."""
    assert check_ambiguity_penalty("Sledding", has_coords=False) == 10
    assert check_ambiguity_penalty("Picnic in Park", has_coords=False) == 15
    assert check_ambiguity_penalty("Beach Day", has_coords=False) == 10
    assert check_ambiguity_penalty("Hiking", has_coords=False) == 15

    # With coords, no penalty applied
    assert check_ambiguity_penalty("Sledding", has_coords=True) is None


def test_check_ambiguity_penalty_brand() -> None:
    """Verifies multi-location commercial brand labels return penalty score <= 30."""
    assert check_ambiguity_penalty("McDonald's", has_coords=False) == 25
    assert check_ambiguity_penalty("Starbucks", has_coords=False) == 25
    assert check_ambiguity_penalty("Subway", has_coords=False) == 30
    assert check_ambiguity_penalty("Walmart Supercenter", has_coords=False) == 25

    # With coords, no penalty applied
    assert check_ambiguity_penalty("Starbucks", has_coords=True) is None


def test_location_resolver_applies_generic_penalty(tmp_path: Path) -> None:
    """Verifies resolver applies penalty and clears address fields for generic label without coords."""
    cache = ScraperCacheManager(db_path=tmp_path / "cache.db")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = (
        '{"poi_name": "Sledding", "street": null, "city": null, '
        '"state_province": null, "postal_code": null, "country": "United States", '
        '"location_confidence_percent": 80}'
    )
    mock_client.models.generate_content.return_value = mock_resp

    resolver = LocationResolver(cache_manager=cache, api_key="dummy-key", genai_client=mock_client)

    path_ctx = ParsedPathContext(poi_name="Sledding", path_tokens=["Sledding"])
    res = resolver.resolve(path_ctx, latitude=None, longitude=None, tags=[])

    assert res.location_confidence_percent <= 15
    assert res.street is None
    assert res.city is None
