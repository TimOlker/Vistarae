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

"""Text normalizer and composite MD5 checksum generator for embeddings (T-026).

Enforces:
- Null coalescing and whitespace collapsing across POI text attributes
- Alphabetically sorted tag formatting
- Deterministic 32-character MD5 checksum computation for change detection
"""

from __future__ import annotations

import hashlib
import re


def normalize_whitespace(text: str) -> str:
    """Collapses consecutive whitespace characters into a single space and strips.

    Args:
        text: Raw text string.

    Returns:
        Cleaned, normalized string.
    """
    return re.sub(r"\s+", " ", text).strip()


def build_composite_text(
    name: str,
    description: str | None = None,
    address: str | None = None,
    city: str | None = None,
    states: list[str] | None = None,
    countries: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Constructs a deterministic composite text payload for vector embedding.

    Args:
        name: POI name (required).
        description: Optional POI description.
        address: Optional address text.
        city: Optional city.
        states: Optional list of states.
        countries: Optional list of countries.
        tags: Optional list of tag names.

    Returns:
        Normalized composite text payload.
    """
    parts: list[str] = [name.strip()]

    if description:
        parts.append(description.strip())
    if address:
        parts.append(address.strip())
    if city:
        parts.append(city.strip())
    if states:
        parts.append(", ".join(sorted(states)))
    if countries:
        parts.append(", ".join(sorted(countries)))
    if tags:
        parts.append(", ".join(sorted(set(t.strip() for t in tags if t.strip()))))

    joined = " | ".join(p for p in parts if p)
    return normalize_whitespace(joined)


def compute_embedding_md5(text: str) -> str:
    """Computes a 32-character hexadecimal MD5 checksum of the normalized text.

    Args:
        text: Composite text payload.

    Returns:
        32-character hex MD5 string.
    """
    normalized = normalize_whitespace(text)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()
