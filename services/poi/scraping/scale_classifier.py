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

"""Spatial scale heuristic classifier (T-034).

Classifies destinations into physical spatial scale tiers:
- Macro: National/State Parks, mountain ranges, forests, large geographic bodies (radius: 5,000m)
- Medium: Museums, zoos, campuses, theme parks, architectural complexes, castles (radius: 500m)
- Micro: Sculptures, monuments, plaques, individual exhibits, viewpoints, gates (radius: 50m)

Implements REQ-EXT-031 for early duplicate detection and parent-child nesting triage.
"""

from __future__ import annotations

import re
from typing import Final, Literal

SpatialScale = Literal["macro", "medium", "micro"]

SCALE_RADII: Final[dict[SpatialScale, float]] = {
    "macro": 5000.0,
    "medium": 500.0,
    "micro": 50.0,
}

SCALE_RANKS: Final[dict[SpatialScale, int]] = {
    "macro": 3,
    "medium": 2,
    "micro": 1,
}

# Micro-scale patterns (sub-attractions, monuments, sculptures, architectural elements)
MICRO_PATTERNS: Final[list[str]] = [
    r"\bsculpture\b",
    r"\bstatue\b",
    r"\bmonument\b",
    r"\bplaque\b",
    r"\bfountain\b",
    r"\broom\b",
    r"\bgallery\b",
    r"\bexhibit\b",
    r"\binstallation\b",
    r"\bbench\b",
    r"\boverlook\b",
    r"\bviewpoint\b",
    r"\bmarker\b",
    r"\bgate\b",
    r"\barch\b",
    r"\btower\b",
    r"\baltar\b",
    r"\brotunda\b",
    r"\bkiosk\b",
    r"\bpavilion\b",
    r"\bbust\b",
    r"\bcolumn\b",
    r"\bstele\b",
    r"\bshrine\b",
    r"\bmemorial\b",
]

# Macro-scale patterns (large natural areas, parks, geographic ranges)
MACRO_PATTERNS: Final[list[str]] = [
    r"\bnational\s+park\b",
    r"\bstate\s+park\b",
    r"\bprovincial\s+park\b",
    r"\bforest\b",
    r"\bwilderness\b",
    r"\bmountain\s+range\b",
    r"\brange\b",
    r"\bvalley\b",
    r"\bcanyon\b",
    r"\bdesert\b",
    r"\barchipelago\b",
    r"\bisland\b",
    r"\bpeninsula\b",
    r"\blake\b",
    r"\bbay\b",
    r"\breserve\b",
    r"\bpark\b",
    r"\btrail\b",
    r"\bbyway\b",
    r"\bhighway\b",
]

# Medium-scale patterns (architectural compounds, institutions, theme parks)
MEDIUM_PATTERNS: Final[list[str]] = [
    r"\bmuseum\b",
    r"\binstitute\b",
    r"\bzoo\b",
    r"\baquarium\b",
    r"\btheme\s+park\b",
    r"\bamusement\s+park\b",
    r"\bcampus\b",
    r"\bbotanical\s+garden\b",
    r"\bgarden\b",
    r"\bresort\b",
    r"\bcomplex\b",
    r"\bstadium\b",
    r"\barena\b",
    r"\bplaza\b",
    r"\bsquare\b",
    r"\bvillage\b",
    r"\bcastle\b",
    r"\bfort\b",
    r"\bfortress\b",
    r"\bpalace\b",
    r"\bcitadel\b",
    r"\bcathedral\b",
    r"\bchurch\b",
    r"\bmonastery\b",
    r"\btemple\b",
    r"\bsanctuary\b",
    r"\bcemetery\b",
    r"\bairport\b",
    r"\bpier\b",
    r"\bharbor\b",
    r"\bwharf\b",
    r"\bmarket\b",
]


class ScaleClassifier:
    """Heuristic classifier determining destination spatial footprint scale."""

    @classmethod
    def get_radius(cls, scale: SpatialScale) -> float:
        """Returns the search and clustering radius in meters for a given scale."""
        return SCALE_RADII.get(scale, 500.0)

    @classmethod
    def is_larger_scale(cls, scale_a: SpatialScale, scale_b: SpatialScale) -> bool:
        """Evaluates whether scale_a encompasses a larger physical footprint than scale_b."""
        return SCALE_RANKS.get(scale_a, 2) > SCALE_RANKS.get(scale_b, 2)

    @classmethod
    def classify_by_name_tags_description(
        cls,
        name: str,
        tags: list[str] | None = None,
        description: str = "",
    ) -> SpatialScale:
        """Classifies by name, tags, and description."""
        return cls.classify(name=name, description=description, tags=tags)

    @classmethod
    def _match_scale(cls, text: str) -> SpatialScale | None:
        """Helper to match text against micro, medium, and macro pattern sets."""
        for pat in MICRO_PATTERNS:
            if re.search(pat, text):
                return "micro"
        for pat in MEDIUM_PATTERNS:
            if re.search(pat, text):
                return "medium"
        for pat in MACRO_PATTERNS:
            if re.search(pat, text):
                return "macro"
        return None

    @classmethod
    def classify(
        cls,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> SpatialScale:
        """Classifies a destination into Macro, Medium, or Micro scale.

        Evaluation order:
        1. Micro-scale keywords in name (sculptures, gates, monuments, viewpoints)
        2. Medium-scale keywords in name (museums, zoos, campuses, castles)
        3. Macro-scale keywords in name (parks, forests, mountain ranges, valleys)
        4. Tag hints
        5. Description keywords
        6. Default fallback to 'medium'

        Args:
            name: POI destination name.
            description: Optional summary or extracted description.
            tags: Optional associated tag slugs or names.

        Returns:
            SpatialScale ('macro', 'medium', or 'micro').
        """
        clean_name = (name or "").strip().lower()
        if scale := cls._match_scale(clean_name):
            return scale

        if tags:
            tag_str = " ".join(t.lower() for t in tags)
            if scale := cls._match_scale(tag_str):
                return scale

        clean_desc = (description or "").strip().lower()
        if clean_desc and (scale := cls._match_scale(clean_desc)):
            return scale

        return "medium"
