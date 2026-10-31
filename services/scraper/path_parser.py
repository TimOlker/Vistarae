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

"""Path parser and directory cleaning heuristics for photo archives (T-015).

Adheres to:
- REQ-SCR-004..007: Noise folder pruning (bad, thumbs, .*, New Folder*, Tim, Maria)
- REQ-SCR-010: Trip To <Country> prefix stripping and gazetteer lookup
- REQ-SCR-011: Parent country/region context injection for child folders
- REQ-SCR-012: Trailing date qualifier stripping (e.g. Japan 4-03 -> Japan)
- REQ-SCR-013: Numerical and single-letter prefix stripping (1-Tokyo, 03 Oaxaca)
- REQ-SCR-014: Parenthetical alternate name extraction (Senso-ji (Asakusa Kannon))
- REQ-SCR-015: Qualified country/city/poi hierarchy tuple construction
- REQ-SCR-016: Illinois home region landmark default heuristics
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from vistarae_core.services.address_normalizer import (
    COUNTRY_MAPPINGS,
    KNOWN_COUNTRIES_LOWER,
)

# Noise directory names in lowercase
_NOISE_FOLDER_NAMES: Final[set[str]] = {
    "bad",
    "thumb",
    "thumbs",
    "thumbnails",
    "resource.frk",
    "misc",
}

# Personal names configured for filtering
_PERSONAL_NAMES: Final[set[str]] = {"tim", "maria"}

# Prefix stripping pattern: number or single letter followed by dash, underscore, or space
_PREFIX_PATTERN: Final[re.Pattern] = re.compile(r"^\s*(?:\d+|[A-Za-z])\s*[-_ ]\s*(.+)$")

# Alternate name parenthetical pattern
_ALTERNATE_NAME_PATTERN: Final[re.Pattern] = re.compile(r"^(.*?)\s*\((.*?)\)\s*$")

# Country date suffix pattern (e.g. "Japan 4-03", "Italy 2018", "France 10-05")
_COUNTRY_DATE_PATTERN: Final[re.Pattern] = re.compile(r"^([A-Za-z\s]+?)\s+\d+(?:[-/]\d+)?$")

# Known regional Illinois landmarks without coordinates (REQ-SCR-016)
_ILLINOIS_LANDMARKS: Final[dict[str, str]] = {
    "garfield park conservatory": "Garfield Park Conservatory",
    "herrik lake": "Herrick Lake",
    "herrick lake": "Herrick Lake",
    "cantigny park": "Cantigny Park",
    "cantigny": "Cantigny Park",
    "starved rock": "Starved Rock State Park",
    "starved rock state park": "Starved Rock State Park",
    "morton arboretum": "Morton Arboretum",
    "lincoln park conservatory": "Lincoln Park Conservatory",
    "millennium park": "Millennium Park",
    "shedd aquarium": "Shedd Aquarium",
    "field museum": "Field Museum",
    "art institute of chicago": "Art Institute of Chicago",
}


@dataclass
class ParsedPathContext:
    """Structured geographic context parsed from a directory path."""

    poi_name: str
    alternate_name: str | None = None
    country: str | None = None
    state_province: str | None = None
    city: str | None = None
    path_tokens: list[str] = field(default_factory=list)


def is_noise_folder(folder_name: str) -> bool:
    """Determines whether a directory matches configured noise patterns.

    Args:
        folder_name: Base name of the directory to evaluate.

    Returns:
        True if the folder is considered noise, False otherwise.
    """
    clean_name = folder_name.strip()
    if not clean_name:
        return True

    # Leading dot (.hidden, .thumbnails)
    if clean_name.startswith("."):
        return True

    lower_name = clean_name.lower()

    # Fixed noise names
    if lower_name in _NOISE_FOLDER_NAMES:
        return True

    # Personal name exclusions
    if lower_name in _PERSONAL_NAMES:
        return True

    # New Folder variations (New Folder, New Folder (2), New Folder (5))
    return lower_name.startswith("new folder")


def strip_segment_prefix(segment: str) -> str:
    """Strips leading numerical or single-letter prefixes (e.g. '1-Tokyo', '03 Oaxaca').

    Args:
        segment: Path segment string.

    Returns:
        Cleaned segment string without prefix.
    """
    match = _PREFIX_PATTERN.match(segment)
    if match:
        remainder = match.group(1).strip()
        if remainder:
            return remainder
    return segment.strip()


def split_alternate_name(name: str) -> tuple[str, str | None]:
    """Splits a folder name with parenthetical content into primary and alternate names.

    Args:
        name: Cleaned folder name string.

    Returns:
        Tuple of (primary_name, alternate_name or None).
    """
    match = _ALTERNATE_NAME_PATTERN.match(name)
    if match:
        primary = match.group(1).strip()
        alt = match.group(2).strip()
        if primary and alt:
            return primary, alt
    return name.strip(), None


def _check_country(token: str) -> str | None:
    """Attempts to match a token against the official country gazetteer.

    Args:
        token: Candidate string token.

    Returns:
        Normalized English country name if recognized, else None.
    """
    cleaned = token.strip()
    if not cleaned:
        return None

    # Check "Trip To <Country>"
    if cleaned.lower().startswith("trip to "):
        cand = cleaned[8:].strip().lower()
        if cand in KNOWN_COUNTRIES_LOWER:
            return COUNTRY_MAPPINGS.get(cand, cand.title())

    # Check "<Country> <date qualifiers>" (e.g. "Japan 4-03")
    date_match = _COUNTRY_DATE_PATTERN.match(cleaned)
    if date_match:
        cand = date_match.group(1).strip().lower()
        if cand in KNOWN_COUNTRIES_LOWER:
            return COUNTRY_MAPPINGS.get(cand, cand.title())

    # Check direct country name
    cand = cleaned.lower()
    if cand in KNOWN_COUNTRIES_LOWER:
        return COUNTRY_MAPPINGS.get(cand, cand.title())

    return None


def parse_path_hierarchy(path: Path | str) -> ParsedPathContext:
    """Parses a directory path into hierarchical geographic components.

    Args:
        path: Path object or string of the candidate POI directory.

    Returns:
        ParsedPathContext with resolved country, city, state, and POI name.
    """
    p = Path(path)
    # Collect parts excluding empty and noise segments
    parts = [part for part in p.parts if part and not is_noise_folder(part)]
    if not parts:
        return ParsedPathContext(poi_name="")

    country: str | None = None
    city: str | None = None
    state_province: str | None = None

    country_idx: int = -1

    # Scan ancestors for country context
    for i, seg in enumerate(parts):
        matched_country = _check_country(seg)
        if matched_country:
            country = matched_country
            country_idx = i
            break

    # The leaf folder represents the candidate POI
    leaf_raw = parts[-1]
    leaf_clean = strip_segment_prefix(leaf_raw)
    poi_name, alt_name = split_alternate_name(leaf_clean)

    # Determine city from intermediate folders between country and leaf
    if country_idx != -1 and country_idx < len(parts) - 1:
        intermediates = parts[country_idx + 1 : -1]
        if intermediates:
            city_candidate = strip_segment_prefix(intermediates[-1])
            if _check_country(city_candidate) is None:
                city = city_candidate
    elif country is None and len(parts) > 1:
        # If country not explicitly identified, previous segment can be city
        city_candidate = strip_segment_prefix(parts[-2])
        if _check_country(city_candidate) is None:
            city = city_candidate

    # Evaluate Illinois home region heuristic (REQ-SCR-016)
    leaf_lower = poi_name.lower()
    if leaf_lower in _ILLINOIS_LANDMARKS:
        poi_name = _ILLINOIS_LANDMARKS[leaf_lower]
        state_province = "Illinois"
        country = "United States"

    # Build tokens list
    tokens: list[str] = []
    if country:
        tokens.append(country)
    if state_province:
        tokens.append(state_province)
    if city:
        tokens.append(city)
    tokens.append(poi_name)
    if alt_name:
        tokens.append(alt_name)

    return ParsedPathContext(
        poi_name=poi_name,
        alternate_name=alt_name,
        country=country,
        state_province=state_province,
        city=city,
        path_tokens=tokens,
    )
