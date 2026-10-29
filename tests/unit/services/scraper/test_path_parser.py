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

"""Unit tests for path parser and directory cleaning heuristics (T-011).

Validates:
- Noise folder pruning (bad, thumbs, .*, New Folder*, Tim, Maria) (REQ-SCR-004..007)
- Trip prefix extraction (Trip To India) (REQ-SCR-010)
- Country date qualifier stripping (Japan 4-03) (REQ-SCR-012)
- Numerical and single letter prefix stripping (1-Tokyo, 03 Oaxaca) (REQ-SCR-013)
- Parenthetical alternate name splitting (Senso-ji (Asakusa Kannon)) (REQ-SCR-014)
- Hierarchical country/city/poi context resolution (REQ-SCR-015)
- Regional Illinois landmark default heuristic (REQ-SCR-016)
"""

from __future__ import annotations

from pathlib import Path

from services.scraper.path_parser import (
    ParsedPathContext,
    is_noise_folder,
    parse_path_hierarchy,
    split_alternate_name,
    strip_segment_prefix,
)


def test_is_noise_folder() -> None:
    """Verifies noise folder filtering matches spec rules."""
    assert is_noise_folder("bad") is True
    assert is_noise_folder("BAD") is True
    assert is_noise_folder("thumb") is True
    assert is_noise_folder("thumbs") is True
    assert is_noise_folder("thumbnails") is True
    assert is_noise_folder("resource.frk") is True
    assert is_noise_folder("RESOURCE.FRK") is True
    assert is_noise_folder("misc") is True
    assert is_noise_folder(".hidden") is True
    assert is_noise_folder(".thumbnails") is True
    assert is_noise_folder("New Folder") is True
    assert is_noise_folder("New Folder (2)") is True
    assert is_noise_folder("New Folder (5)") is True
    assert is_noise_folder("Tim") is True
    assert is_noise_folder("Maria") is True
    assert is_noise_folder("maria") is True

    # Valid folders should not be noise
    assert is_noise_folder("Tokyo") is False
    assert is_noise_folder("Trip To India") is False
    assert is_noise_folder("Monte Alban") is False


def test_strip_segment_prefix() -> None:
    """Verifies numerical and alphabetical prefix stripping."""
    assert strip_segment_prefix("1-Tokyo") == "Tokyo"
    assert strip_segment_prefix("1 - Fussen") == "Fussen"
    assert strip_segment_prefix("A-Kobe") == "Kobe"
    assert strip_segment_prefix("03 Oaxaca") == "Oaxaca"
    assert strip_segment_prefix("03 Monte Alban") == "Monte Alban"
    assert strip_segment_prefix("12-Kyoto") == "Kyoto"
    assert strip_segment_prefix("Plain Name") == "Plain Name"


def test_split_alternate_name() -> None:
    """Verifies extraction of primary name and parenthetical alternate name."""
    primary, alt = split_alternate_name("Senso-ji (Asakusa Kannon Temple)")
    assert primary == "Senso-ji"
    assert alt == "Asakusa Kannon Temple"

    primary, alt = split_alternate_name("Bamburgh Castle")
    assert primary == "Bamburgh Castle"
    assert alt is None


def test_parse_path_hierarchy_trip_to() -> None:
    """Verifies 'Trip To <Country>' extracts country context for child folders."""
    p = Path("Trip To India/01 Delhi/Red Fort")
    ctx: ParsedPathContext = parse_path_hierarchy(p)
    assert ctx.country == "India"
    assert ctx.city == "Delhi"
    assert ctx.poi_name == "Red Fort"


def test_parse_path_hierarchy_country_with_date() -> None:
    """Verifies 'Japan 4-03/1-Tokyo/Senso-ji (Asakusa Kannon)' parses country, city, POI, alt."""
    p = Path("Japan 4-03/1-Tokyo/Senso-ji (Asakusa Kannon)")
    ctx: ParsedPathContext = parse_path_hierarchy(p)
    assert ctx.country == "Japan"
    assert ctx.city == "Tokyo"
    assert ctx.poi_name == "Senso-ji"
    assert ctx.alternate_name == "Asakusa Kannon"


def test_parse_path_hierarchy_nested_mexico() -> None:
    """Verifies 'Mexico/03 Oaxaca/03 Monte Alban' constructs qualified hierarchy."""
    p = Path("Photos/Mexico/03 Oaxaca/03 Monte Alban")
    ctx: ParsedPathContext = parse_path_hierarchy(p)
    assert ctx.country == "Mexico"
    assert ctx.city == "Oaxaca"
    assert ctx.poi_name == "Monte Alban"


def test_parse_path_hierarchy_illinois_landmark_fallback() -> None:
    """Verifies default Illinois state context for known home region landmarks."""
    p = Path("Midwest/Garfield Park Conservatory")
    ctx = parse_path_hierarchy(p)
    assert ctx.poi_name == "Garfield Park Conservatory"
    assert ctx.state_province == "Illinois"
    assert ctx.country == "United States"

    p2 = Path("Herrik Lake")
    ctx2 = parse_path_hierarchy(p2)
    assert ctx2.poi_name in ("Herrik Lake", "Herrick Lake")
    assert ctx2.state_province == "Illinois"
    assert ctx2.country == "United States"

