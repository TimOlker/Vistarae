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

"""Test fixtures providing complete candidate objects and export data for 017-export."""

from __future__ import annotations

from typing import Any
from uuid import UUID

SAMPLE_PARENT_UUID = UUID("11111111-1111-1111-1111-111111111111")
SAMPLE_CANDIDATE_1_UUID = UUID("22222222-2222-2222-2222-222222222222")
SAMPLE_CANDIDATE_2_UUID = UUID("33333333-3333-3333-3333-333333333333")
SAMPLE_MERGE_TARGET_UUID = UUID("44444444-4444-4444-4444-444444444444")


def get_sample_staged_candidates() -> list[dict[str, Any]]:
    """Returns a representative list of staged candidates with all 35+ attributes populated."""
    return [
        {
            "candidate_id": SAMPLE_PARENT_UUID,
            "id": SAMPLE_PARENT_UUID,
            "row_index": 1,
            "poi_name": "Yellowstone National Park",
            "street_address": "2 Officers Row",
            "city": "Yellowstone National Park",
            "locality": "Mammoth Hot Springs",
            "admin_level_2": "Park County",
            "admin_level_1": "Wyoming",
            "state_province": "Wyoming",
            "postal_code": "82190",
            "country": "United States",
            "country_code": "US",
            "latitude": 44.427963,
            "longitude": -110.588455,
            "recommended_disposition": "accept",
            "user_disposition": "accept",
            "confidence_score": 95,
            "disposition_justification": "Verified authoritative national park coordinates.",
            "description": "America's first national park, featuring vast wilderness and geysers.",
            "reason_to_visit": "Iconic geothermal features and wildlife watching.",
            "hero_image_url": "https://example.com/yellowstone_hero.jpg",
            "official_url": "https://www.nps.gov/yell/index.htm",
            "wiki_url": "https://en.wikipedia.org/wiki/Yellowstone_National_Park",
            "related_websites": [
                {"name": "NPS Official", "url": "https://www.nps.gov/yell"},
                {"name": "Lodging Guide", "url": "https://www.yellowstonenationalparklodges.com"},
            ],
            "no_websites": False,
            "tags": ["National Park", "Geyser", "Wildlife", "Scenic"],
            "photo_directory": "D:/Photos/Yellowstone/2024",
            "photo_directories": ["D:/Photos/Yellowstone/2024", "D:/Photos/Yellowstone/2022"],
            "dates_visited": ["2022-07-15", "2024-08-10"],
            "recommended_duration_hours": 8.0,
            "recommended_visit_days": 3,
            "estimated_visit_time_notes": "Spend at least 3 full days to tour Upper and Lower loops.",
            "parent_candidate_id": None,
            "parent_poi_id": None,
            "matched_existing_poi_id": None,
            "merge_target_id": None,
            "is_user_overridden": True,
        },
        {
            "candidate_id": SAMPLE_CANDIDATE_1_UUID,
            "id": SAMPLE_CANDIDATE_1_UUID,
            "row_index": 2,
            "poi_name": "=Grand Prismatic Spring",
            "street_address": "Midway Geyser Basin",
            "city": "Yellowstone National Park",
            "locality": "Midway",
            "admin_level_2": "Teton County",
            "admin_level_1": "Wyoming",
            "state_province": "Wyoming",
            "postal_code": "82190",
            "country": "United States",
            "country_code": "US",
            "latitude": 44.525049,
            "longitude": -110.838190,
            "recommended_disposition": "sublocation",
            "user_disposition": "sublocation",
            "confidence_score": 90,
            "disposition_justification": "+Sublocation nested within Yellowstone macro-site.",
            "description": "@Largest hot spring in the United States, famous for vibrant rainbow colors.",
            "reason_to_visit": "-Stunning aerial and boardwalk perspectives of microbial mats.",
            "hero_image_url": "https://example.com/grand_prismatic.jpg",
            "official_url": "",
            "wiki_url": "https://en.wikipedia.org/wiki/Grand_Prismatic_Spring",
            "related_websites": [
                {
                    "name": "Midway Geyser Basin",
                    "url": "https://www.nps.gov/yell/learn/nature/midway-geyser-basin.htm",
                }
            ],
            "no_websites": False,
            "tags": ["Hot Spring", "Thermal", "Geology"],
            "photo_directory": "D:/Photos/Yellowstone/2024/Midway",
            "photo_directories": ["D:/Photos/Yellowstone/2024/Midway"],
            "dates_visited": ["2024-08-11"],
            "recommended_duration_hours": 2.0,
            "recommended_visit_days": 1,
            "estimated_visit_time_notes": "Hike the Fairy Falls overlook trail for the best view.",
            "parent_candidate_id": SAMPLE_PARENT_UUID,
            "parent_poi_id": None,
            "matched_existing_poi_id": None,
            "merge_target_id": None,
            "is_user_overridden": True,
        },
    ]
