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

"""Default Tag Seeder Service (REQ-EXT-003, T-009).

Seeds 30 standardized default tags with immutable slugs and search aliases
for newly registered or provisioned users.
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.tables import TagTable

DEFAULT_TAGS: list[dict[str, Any]] = [
    {
        "slug": "fortification",
        "name": "Fortification",
        "aliases": ["castle", "fort", "citadel", "fortress"],
    },
    {
        "slug": "landmark",
        "name": "Landmark",
        "aliases": ["monument", "obelisk", "tower"],
    },
    {
        "slug": "ship",
        "name": "Ship",
        "aliases": ["boat", "vessel", "submarine", "warship", "museum ship"],
    },
    {
        "slug": "aircraft",
        "name": "Aircraft",
        "aliases": ["airplane", "plane", "jet", "aviation"],
    },
    {
        "slug": "military",
        "name": "Military",
        "aliases": ["battlefield", "base", "bunker", "armory", "fort"],
    },
    {
        "slug": "rail",
        "name": "Rail",
        "aliases": ["train", "railway", "locomotive", "funicular", "tram"],
    },
    {
        "slug": "historic",
        "name": "Historic",
        "aliases": ["history", "heritage", "ancient", "antique"],
    },
    {
        "slug": "memorial",
        "name": "Memorial",
        "aliases": ["shrine", "cenotaph", "tribute", "cemetery"],
    },
    {
        "slug": "building",
        "name": "Building",
        "aliases": ["skyscraper", "hall", "palace", "estate"],
    },
    {
        "slug": "church",
        "name": "Church",
        "aliases": ["cathedral", "chapel", "basilica"],
    },
    {
        "slug": "temple",
        "name": "Temple",
        "aliases": ["pagoda", "shrine", "sanctuary", "mosque", "synagogue"],
    },
    {
        "slug": "museum",
        "name": "Museum",
        "aliases": ["gallery", "exhibition", "archive"],
    },
    {
        "slug": "scenic",
        "name": "Scenic",
        "aliases": ["overlook", "view", "vista", "panoramic"],
    },
    {
        "slug": "waterfall",
        "name": "Waterfall",
        "aliases": ["falls", "cascade", "cataract"],
    },
    {
        "slug": "water",
        "name": "Water",
        "aliases": ["lake", "river", "spring", "reservoir", "lagoon"],
    },
    {
        "slug": "park",
        "name": "Park",
        "aliases": ["public park", "gardens", "arboretum", "botanic"],
    },
    {
        "slug": "wilderness",
        "name": "Wilderness",
        "aliases": ["nature reserve", "wildlife refuge", "canyon"],
    },
    {
        "slug": "coast",
        "name": "Coast",
        "aliases": ["beach", "shoreline", "cliff", "cove", "bay"],
    },
    {
        "slug": "mountain",
        "name": "Mountain",
        "aliases": ["peak", "summit", "ridge", "pass", "volcano"],
    },
    {
        "slug": "food",
        "name": "Food",
        "aliases": ["dining", "restaurant", "cafe", "bakery", "market", "brewery"],
    },
    {
        "slug": "nps",
        "name": "NPS",
        "aliases": ["national park", "national monument", "national seashore"],
    },
    {
        "slug": "unesco",
        "name": "UNESCO",
        "aliases": ["world heritage", "unesco site"],
    },
    {
        "slug": "culture",
        "name": "Culture",
        "aliases": ["art", "folklore", "theater", "music", "festival"],
    },
    {
        "slug": "lighthouse",
        "name": "Lighthouse",
        "aliases": ["light station", "beacon"],
    },
    {
        "slug": "zoo",
        "name": "Zoo",
        "aliases": ["zoological park", "safari", "menagerie"],
    },
    {
        "slug": "animal",
        "name": "Animal",
        "aliases": ["wildlife", "sanctuary", "aquarium", "aviary"],
    },
    {
        "slug": "shopping",
        "name": "Shopping",
        "aliases": ["mall", "bazaar", "boutique", "antique shop"],
    },
    {
        "slug": "entertainment",
        "name": "Entertainment",
        "aliases": ["theme park", "amusement", "casino"],
    },
    {
        "slug": "film_location",
        "name": "Film Location",
        "aliases": ["movie location", "filming site", "cinema"],
    },
    {
        "slug": "humorous",
        "name": "Humorous",
        "aliases": ["quirky", "roadside attraction", "novelty", "oddity"],
    },
]


async def seed_default_tags(user_id: UUID, session: AsyncSession) -> int:
    """Seeds the 30 standardized default tags for a user.

    Enforces idempotent insertion via ON CONFLICT (user_id, slug) DO NOTHING.

    Args:
        user_id: Target tenant UUID.
        session: Active SQLAlchemy AsyncSession.

    Returns:
        Number of tags inserted or present.
    """
    records = [
        {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "name": tag["name"],
            "slug": tag["slug"],
            "aliases": tag["aliases"],
        }
        for tag in DEFAULT_TAGS
    ]

    stmt = (
        pg_insert(TagTable)
        .values(records)
        .on_conflict_do_nothing(index_elements=["user_id", "slug"])
    )
    await session.execute(stmt)
    await session.flush()
    return len(records)
