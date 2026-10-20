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

"""Local database seeding script (T-052).

Creates test users across low, high, and admin tiers, along with realistic
POIs (including multi-state, multi-country, and macro/child hierarchies),
curated lists, taxonomy tags, and geocoding cache records.

Enforces Constitution Principle 6: Strictly verifies STAGE == 'local' before
performing any destructive or seeding operations.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete
from vistarae_core.adapters.db.session import _get_session_factory, init_engine
from vistarae_core.adapters.db.tables import (
    GeocodingCacheTable,
    ListTable,
    POIListTable,
    POITable,
    POITagTable,
    TagTable,
    UserMetricsTable,
    UserPreferencesTable,
    UserQuotasTable,
    UserTable,
)
from vistarae_core.adapters.embedding.mock import MockEmbeddingAdapter
from vistarae_core.adapters.repositories.geocache_repo import (
    hash_query_string,
)
from vistarae_core.domain.value_objects import EnrichmentStatus, VisitState
from vistarae_core.services.embedding_sanitizer import (
    build_composite_text,
    compute_embedding_md5,
)

SEED_USERS = [
    {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "cognito_sub": "00000000-0000-0000-0000-000000000001",
        "email": "low-tier@local.vistarae.dev",
        "full_name": "Low Tier Traveler",
        "tier": "low",
        "monthly_token_quota": 50000,
    },
    {
        "id": UUID("00000000-0000-0000-0000-000000000002"),
        "cognito_sub": "00000000-0000-0000-0000-000000000002",
        "email": "high-tier@local.vistarae.dev",
        "full_name": "High Tier Traveler",
        "tier": "high",
        "monthly_token_quota": 200000,
    },
    {
        "id": UUID("00000000-0000-0000-0000-000000000003"),
        "cognito_sub": "00000000-0000-0000-0000-000000000003",
        "email": "admin@local.vistarae.dev",
        "full_name": "Admin Operator",
        "tier": "admin",
        "monthly_token_quota": 1000000,
    },
]

SEED_TAGS = [
    "hiking",
    "scenic-view",
    "waterfall",
    "national-park",
    "camping",
    "roadtrip-2026",
    "photography",
    "mountain",
]

SEED_LISTS = [
    {
        "id": UUID("10000000-0000-0000-0000-000000000001"),
        "title": "California National Parks & Sights",
        "description": "Scenic icons, peaks, and alpine vistas across California.",
        "is_public": True,
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000002"),
        "title": "Great American Road Trip",
        "description": "Multi-state bucket-list destinations from coast to coast.",
        "is_public": False,
    },
]

# Hierarchical POI definitions
YOSEMITE_ID = UUID("20000000-0000-0000-0000-000000000001")
GLACIER_POINT_ID = UUID("20000000-0000-0000-0000-000000000002")
HALF_DOME_ID = UUID("20000000-0000-0000-0000-000000000003")
ZION_ID = UUID("20000000-0000-0000-0000-000000000004")
ANGELS_LANDING_ID = UUID("20000000-0000-0000-0000-000000000005")
YELLOWSTONE_ID = UUID("20000000-0000-0000-0000-000000000006")
LAKE_TAHOE_ID = UUID("20000000-0000-0000-0000-000000000007")
NIAGARA_FALLS_ID = UUID("20000000-0000-0000-0000-000000000008")
BANFF_ID = UUID("20000000-0000-0000-0000-000000000009")

SEED_POIS = [
    {
        "id": YOSEMITE_ID,
        "name": "Yosemite National Park",
        "parent_poi_id": None,
        "lon": -119.5383,
        "lat": 37.8651,
        "description": "Iconic Sierra Nevada national park renowned for dramatic granite peaks, giant sequoias, and roaring waterfalls.",
        "address": "Yosemite National Park, CA 95389",
        "city": "Yosemite Valley",
        "states": ["California"],
        "countries": ["United States"],
        "visit_state": VisitState.VISITED_RETURN.value,
        "rating": 5,
        "recommended_duration_hours": 8.0,
        "recommended_visit_days": 3,
        "tags": ["national-park", "hiking", "scenic-view", "photography"],
        "lists": [SEED_LISTS[0]["id"], SEED_LISTS[1]["id"]],
    },
    {
        "id": GLACIER_POINT_ID,
        "name": "Glacier Point Overlook",
        "parent_poi_id": YOSEMITE_ID,
        "lon": -119.5732,
        "lat": 37.7303,
        "description": "Breathtaking scenic overlook commanding panoramic vistas of Yosemite Valley, Half Dome, and Yosemite Falls.",
        "address": "Glacier Point Rd, Yosemite National Park, CA 95389",
        "city": "Yosemite Valley",
        "states": ["California"],
        "countries": ["United States"],
        "visit_state": VisitState.VISITED_RETURN.value,
        "rating": 5,
        "recommended_duration_hours": 2.5,
        "recommended_visit_days": 1,
        "tags": ["scenic-view", "photography", "mountain"],
        "lists": [SEED_LISTS[0]["id"]],
    },
    {
        "id": HALF_DOME_ID,
        "name": "Half Dome",
        "parent_poi_id": YOSEMITE_ID,
        "lon": -119.5332,
        "lat": 37.7460,
        "description": "World-famous granite dome rising nearly 5,000 feet above Yosemite Valley floor with cable route.",
        "address": "Half Dome Trail, Yosemite National Park, CA 95389",
        "city": "Yosemite Valley",
        "states": ["California"],
        "countries": ["United States"],
        "visit_state": VisitState.NOT_VISITED.value,
        "rating": 5,
        "recommended_duration_hours": 10.0,
        "recommended_visit_days": 1,
        "tags": ["hiking", "mountain", "scenic-view"],
        "lists": [SEED_LISTS[0]["id"]],
    },
    {
        "id": ZION_ID,
        "name": "Zion National Park",
        "parent_poi_id": None,
        "lon": -113.0263,
        "lat": 37.2982,
        "description": "Southwest Utah wonderland known for soaring red Navajo sandstone cliffs and slot canyons.",
        "address": "1 Zion Park Blvd, Springdale, UT 84767",
        "city": "Springdale",
        "states": ["Utah"],
        "countries": ["United States"],
        "visit_state": VisitState.NOT_VISITED.value,
        "rating": 5,
        "recommended_duration_hours": 7.0,
        "recommended_visit_days": 2,
        "tags": ["national-park", "hiking", "scenic-view"],
        "lists": [SEED_LISTS[1]["id"]],
    },
    {
        "id": ANGELS_LANDING_ID,
        "name": "Angels Landing",
        "parent_poi_id": ZION_ID,
        "lon": -112.9479,
        "lat": 37.2691,
        "description": "Thrilling knife-edge ridge hike with chained handrails overlooking Zion Canyon.",
        "address": "Angels Landing Trail, Springdale, UT 84767",
        "city": "Springdale",
        "states": ["Utah"],
        "countries": ["United States"],
        "visit_state": VisitState.NOT_VISITED.value,
        "rating": 5,
        "recommended_duration_hours": 4.5,
        "recommended_visit_days": 1,
        "tags": ["hiking", "scenic-view", "photography"],
        "lists": [SEED_LISTS[1]["id"]],
    },
    {
        "id": YELLOWSTONE_ID,
        "name": "Yellowstone National Park",
        "parent_poi_id": None,
        "lon": -110.5885,
        "lat": 44.4280,
        "description": "First national park in the world, spanning three states with geothermal features and abundant wildlife.",
        "address": "Yellowstone National Park, WY 82190",
        "city": "Yellowstone National Park",
        "states": ["Wyoming", "Montana", "Idaho"],  # Multi-state POI!
        "countries": ["United States"],
        "visit_state": VisitState.NOT_VISITED.value,
        "rating": 5,
        "recommended_duration_hours": 8.0,
        "recommended_visit_days": 4,
        "tags": ["national-park", "scenic-view", "camping", "roadtrip-2026"],
        "lists": [SEED_LISTS[1]["id"]],
    },
    {
        "id": LAKE_TAHOE_ID,
        "name": "Lake Tahoe",
        "parent_poi_id": None,
        "lon": -120.0324,
        "lat": 39.0968,
        "description": "Massive alpine freshwater lake straddling California and Nevada, famed for cobalt blue water and surrounding peaks.",
        "address": "Lake Tahoe, CA / NV",
        "city": "South Lake Tahoe",
        "states": ["California", "Nevada"],  # Multi-state POI!
        "countries": ["United States"],
        "visit_state": VisitState.VISITED_RETURN.value,
        "rating": 5,
        "recommended_duration_hours": 6.0,
        "recommended_visit_days": 3,
        "tags": ["scenic-view", "camping", "photography", "roadtrip-2026"],
        "lists": [SEED_LISTS[0]["id"], SEED_LISTS[1]["id"]],
    },
    {
        "id": NIAGARA_FALLS_ID,
        "name": "Niagara Falls",
        "parent_poi_id": None,
        "lon": -79.0377,
        "lat": 43.0896,
        "description": "Massive three-waterfall system spanning the international border between New York and Ontario.",
        "address": "Niagara Falls, NY 14303 / Niagara Falls, ON",
        "city": "Niagara Falls",
        "states": ["New York", "Ontario"],  # Multi-state POI!
        "countries": ["United States", "Canada"],  # Multi-country POI!
        "visit_state": VisitState.VISITED_DO_NOT_RETURN.value,
        "rating": 4,
        "recommended_duration_hours": 3.0,
        "recommended_visit_days": 1,
        "tags": ["waterfall", "scenic-view", "roadtrip-2026"],
        "lists": [SEED_LISTS[1]["id"]],
    },
    {
        "id": BANFF_ID,
        "name": "Banff National Park",
        "parent_poi_id": None,
        "lon": -115.5708,
        "lat": 51.1784,
        "description": "Canada's oldest national park in the Alberta Rocky Mountains with glacial turquoise lakes and snow-capped peaks.",
        "address": "Banff, AB T1L 1K2",
        "city": "Banff",
        "states": ["Alberta"],
        "countries": ["Canada"],
        "visit_state": VisitState.NOT_VISITED.value,
        "rating": 5,
        "recommended_duration_hours": 8.0,
        "recommended_visit_days": 3,
        "tags": ["national-park", "hiking", "mountain", "photography"],
        "lists": [SEED_LISTS[1]["id"]],
    },
]


async def seed_local_db() -> None:
    """Seeds test users, POIs, lists, tags, and geocoding cache in local database."""
    stage = os.getenv("STAGE", "local")
    if stage != "local":
        raise RuntimeError(
            f"Database seeding is strictly permitted only when STAGE == 'local'. Current STAGE='{stage}'."
        )

    await init_engine()
    factory = _get_session_factory()
    now = datetime.now(UTC)
    embedder = MockEmbeddingAdapter()

    async with factory() as session:
        # 1. Clean existing records for seed users
        user_ids = [s["id"] for s in SEED_USERS]
        await session.execute(delete(POITable).where(POITable.user_id.in_(user_ids)))
        await session.execute(delete(ListTable).where(ListTable.user_id.in_(user_ids)))
        await session.execute(delete(TagTable).where(TagTable.user_id.in_(user_ids)))
        await session.execute(delete(UserTable).where(UserTable.id.in_(user_ids)))

        # 2. Seed Users
        for seed in SEED_USERS:
            user_row = UserTable(
                id=seed["id"],
                cognito_sub=seed["cognito_sub"],
                email=seed["email"],
                full_name=seed["full_name"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            pref_row = UserPreferencesTable(user_id=seed["id"], created_at=now, updated_at=now)
            metric_row = UserMetricsTable(user_id=seed["id"], updated_at=now)
            quota_row = UserQuotasTable(
                user_id=seed["id"],
                tier=seed["tier"],
                monthly_token_quota=seed["monthly_token_quota"],
                current_token_usage=0,
                request_count=0,
                window_start_at=now,
                is_disabled=False,
                updated_at=now,
            )
            session.add_all([user_row, pref_row, metric_row, quota_row])

        # 3. Seed Tags for primary user (low-tier traveler)
        primary_user_id = SEED_USERS[0]["id"]
        tag_id_map: dict[str, UUID] = {}
        for tag_name in SEED_TAGS:
            tag_id = uuid4()
            tag_id_map[tag_name] = tag_id
            session.add(
                TagTable(
                    id=tag_id,
                    user_id=primary_user_id,
                    name=tag_name,
                    created_at=now,
                )
            )

        # 4. Seed Curated Lists for primary user
        for list_item in SEED_LISTS:
            session.add(
                ListTable(
                    id=list_item["id"],
                    user_id=primary_user_id,
                    title=list_item["title"],
                    description=list_item["description"],
                    is_public=list_item["is_public"],
                    created_at=now,
                    updated_at=now,
                )
            )

        # 5. Seed POIs, associations, and embeddings
        for p in SEED_POIS:
            comp_text = build_composite_text(
                name=p["name"],
                description=p["description"],
                address=p["address"],
                city=p["city"],
                states=p["states"],
                countries=p["countries"],
                tags=p["tags"],
            )
            vector = await embedder.generate_embedding(comp_text)
            md5_checksum = compute_embedding_md5(comp_text)

            geom_wkt = WKTElement(f"POINT({p['lon']} {p['lat']})", srid=4326)

            poi_row = POITable(
                id=p["id"],
                user_id=primary_user_id,
                parent_poi_id=p["parent_poi_id"],
                name=p["name"],
                geom=geom_wkt,
                description=p["description"],
                address=p["address"],
                city=p["city"],
                states=p["states"],
                countries=p["countries"],
                visit_state=p["visit_state"],
                rating=p["rating"],
                recommended_duration_hours=p["recommended_duration_hours"],
                recommended_visit_days=p["recommended_visit_days"],
                enrichment_status=EnrichmentStatus.SUCCESS.value,
                embedding=vector,
                embedding_md5=md5_checksum,
                created_at=now,
                updated_at=now,
            )
            session.add(poi_row)

        await session.flush()

        # Link tags and lists
        for p in SEED_POIS:
            for t_name in p["tags"]:
                if t_name in tag_id_map:
                    session.add(
                        POITagTable(
                            poi_id=p["id"],
                            tag_id=tag_id_map[t_name],
                        )
                    )

            for list_id in p["lists"]:
                session.add(
                    POIListTable(
                        poi_id=p["id"],
                        list_id=list_id,
                        added_at=now,
                    )
                )

        # 6. Seed Geocoding Cache entries
        cache_samples = [
            (
                "Yosemite National Park",
                37.8651,
                -119.5383,
                "Yosemite National Park, California, United States",
            ),
            ("Lake Tahoe", 39.0968, -120.0324, "Lake Tahoe, California / Nevada, United States"),
            (
                "Yellowstone National Park",
                44.4280,
                -110.5885,
                "Yellowstone National Park, WY / MT / ID, United States",
            ),
        ]
        sample_hashes = [hash_query_string(q) for q, _, _, _ in cache_samples]
        await session.execute(
            delete(GeocodingCacheTable).where(GeocodingCacheTable.query_hash.in_(sample_hashes))
        )
        for query, lat, lon, formatted in cache_samples:
            q_hash = hash_query_string(query)
            session.add(
                GeocodingCacheTable(
                    query_hash=q_hash,
                    lat=lat,
                    lon=lon,
                    formatted_address=formatted,
                    status="SUCCESS",
                    created_at=now,
                    expires_at=now + timedelta(days=90),
                )
            )

        await session.commit()

    print(
        f"Successfully seeded {len(SEED_USERS)} users, {len(SEED_POIS)} POIs, "
        f"{len(SEED_LISTS)} lists, and {len(SEED_TAGS)} tags."
    )


if __name__ == "__main__":
    try:
        asyncio.run(seed_local_db())
    except Exception as exc:
        print(f"Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)
