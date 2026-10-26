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

"""Tag recommendation matching engine (REQ-EXT-029, T-027).

Matches scraped page text and synthesized summaries against the user's vetted
tag library (slugs, display names, and searchable aliases), supporting
overlapping aliases recommending all candidate tags.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any


class TagMatcher:
    """Matches text content against vetted tag definitions."""

    def __init__(self, tags: Sequence[dict[str, Any]] | Sequence[Any]) -> None:
        """Initializes matcher with user's vetted tags.

        Args:
            tags: List of tag dictionaries or ORM/schema objects having
                  `slug`, `name`, and `aliases`.
        """
        self._tag_definitions: list[dict[str, Any]] = []
        for tag in tags:
            if isinstance(tag, dict):
                self._tag_definitions.append(tag)
            else:
                self._tag_definitions.append(
                    {
                        "slug": getattr(tag, "slug", ""),
                        "name": getattr(tag, "name", ""),
                        "aliases": getattr(tag, "aliases", []) or [],
                    }
                )

    def match_tags(self, text: str) -> list[str]:
        """Matches text against tag names, slugs, and aliases.

        Supports overlapping aliases where an alias (e.g. 'castle') may
        trigger recommendations for multiple candidate tags (REQ-EXT-029).

        Args:
            text: Scraped or synthesized text (name, description, page text).

        Returns:
            List of unique matched tag slugs.
        """
        if not text:
            return []

        normalized_text = text.lower()
        matched_slugs: set[str] = set()

        for tag in self._tag_definitions:
            slug = tag.get("slug")
            name = tag.get("name", "")
            aliases = tag.get("aliases", []) or []

            if not slug:
                continue

            # Candidate keywords for this tag
            keywords = {slug.lower().replace("_", " "), name.lower()}
            for alias in aliases:
                if alias:
                    keywords.add(alias.lower())

            # Check boundary match for any keyword
            for keyword in keywords:
                if not keyword:
                    continue
                # Regex word boundary check: keyword surrounded by non-alphanumeric or start/end
                pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"
                if re.search(pattern, normalized_text):
                    matched_slugs.add(slug)
                    break

        return sorted(matched_slugs)
