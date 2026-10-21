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

import argparse
import os
import sys
import requests

from common import deduplicate_tags, write_standard_csv

API_KEY = os.environ.get("NPS_API_KEY", "DEMO_KEY")
BASE_URL = "https://developer.nps.gov/api/v1/parks"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "nps_sites.csv")


def extract_city_state(park: dict) -> tuple[str, str]:
    """Extract primary city and state from postal or physical addresses."""
    addresses = park.get("addresses", [])
    if not addresses:
        # Fall back to top-level states string (e.g. 'WY,MT,ID')
        states = park.get("states", "")
        primary_state = states.split(",")[0] if states else ""
        return "", primary_state

    # Prioritize Physical address, then Postal
    target_addr = next(
        (a for a in addresses if a.get("type") == "Physical"), addresses[0]
    )
    city = target_addr.get("city", "").strip()
    state = target_addr.get("stateCode", "").strip()
    return city, state


def determine_park_site_type(title: str, designation: str) -> str:
    """Determine the specific NPS unit type from designation and title."""
    d_clean = (designation or "").strip()
    t_clean = (title or "").strip()
    combined = f"{d_clean} {t_clean}".lower()

    if "national historic site" in combined:
        return "National Historic Site"
    if "national historical park" in combined or "national historic park" in combined:
        return "National Historical Park"
    if "national military park" in combined:
        return "National Military Park"
    if "national battlefield park" in combined:
        return "National Battlefield Park"
    if "national battlefield site" in combined:
        return "National Battlefield Site"
    if "national battlefield" in combined:
        return "National Battlefield"
    if "national historic trail" in combined:
        return "National Historic Trail"
    if "national scenic trail" in combined:
        return "National Scenic Trail"
    if "national historical reserve" in combined:
        return "National Historical Reserve"
    if "national historic area" in combined:
        return "National Historic Area"
    if "national seashore" in combined:
        return "National Seashore"
    if "national lakeshore" in combined:
        return "National Lakeshore"
    if "national recreation area" in combined:
        return "National Recreation Area"
    if "national wild and scenic river" in combined or "wild and scenic river" in combined:
        return "National Wild and Scenic River"
    if "national scenic river" in combined:
        return "National Scenic River"
    if "national river" in combined or "wild river" in combined:
        return "National River"
    if "national monument & preserve" in combined or "national monument and preserve" in combined:
        return "National Monument & Preserve"
    if "national monument" in combined:
        return "National Monument"
    if "national memorial" in combined:
        return "National Memorial"
    if "national park & preserve" in combined or "national park and preserve" in combined:
        return "National Park & Preserve"
    if "national park" in combined:
        return "National Park"
    if "national preserve" in combined:
        return "National Preserve"
    if "national reserve" in combined:
        return "National Reserve"
    if "national heritage area" in combined or "national heritage corridor" in combined:
        return "National Heritage Area"
    if "parkway" in combined:
        return "Parkway"
    if "memorial" in combined:
        return "National Memorial"
    if d_clean and d_clean.lower() != "national park system unit":
        return d_clean
    if "park" in combined:
        return "Park"
    return "National Park System Unit"


def generate_tags(park: dict) -> str:
    """Generate comma-separated tags for an NPS park.

    Structure:
    1. 'NPS'
    2. Specific park site type (e.g. National Historic Site, National Park, etc.)
    3. Primary common tags: 'Military', 'Historic', 'Cultural', 'Building', 'Nature'
    4. Succinct descriptors: 'Scenic', 'Coastal', 'Mountain', 'Canyon', 'Desert', 'Cave', 'Water', 'Wildlife'
    """
    title = park.get("fullName", "").strip()
    designation = park.get("designation", "").strip()
    desc = park.get("description", "").strip()
    site_type = determine_park_site_type(title, designation)

    # Collect topics and activities names
    topics = [t.get("name", "").strip() for t in park.get("topics", []) if isinstance(t, dict)]
    topics_lower = {t.lower() for t in topics if t}
    text_corpus = f"{title} {designation} {desc}".lower()

    tags: list[str] = ["NPS"]

    # Park site type tag
    if site_type and site_type != "National Park System Unit":
        tags.append(site_type)

    # 1. Military
    is_military = False
    military_types = {
        "national battlefield",
        "national battlefield park",
        "national battlefield site",
        "national military park",
    }
    if site_type.lower() in military_types:
        is_military = True
    elif any(
        t in topics_lower
        for t in [
            "military", "civil war", "american revolution", "wars and conflicts",
            "world war i", "world war ii", "forts", "war of 1812", "cold war", "veterans"
        ]
    ):
        is_military = True
    elif any(
        kw in text_corpus
        for kw in [
            "battlefield", "military", "fort ", "fortress", "troops", "warfare",
            "confederate", "union army", "infantry", "arsenal", "garrison", "naval battle"
        ]
    ):
        is_military = True

    if is_military:
        tags.append("Military")

    # 2. Historic
    is_historic = False
    historic_types = {
        "national historic site",
        "national historical park",
        "national historic trail",
        "national historic area",
        "national historical reserve",
        "national memorial",
        "national battlefield",
        "national battlefield park",
        "national battlefield site",
        "national military park",
        "national monument",
        "national heritage area",
    }
    if site_type.lower() in historic_types:
        is_historic = True
    elif any(
        t in topics_lower
        for t in [
            "archeology", "birthplace", "presidents", "monuments and memorials",
            "burial, cemetery and gravesite", "colonization and settlement",
            "historic preservation", "maritime history", "westward expansion",
            "women's history", "african american heritage", "indigenous peoples",
            "native american heritage", "asian american heritage", "latino american heritage",
            "industry", "mining", "railroads", "transportation", "explorers", "pioneers",
            "civil rights"
        ]
    ):
        is_historic = True
    elif any(
        kw in text_corpus
        for kw in [
            "historic", "historical", "history", "ancient", "archeolog", "heritage",
            "preservation", "memorial", "monument", "century", "birthplace", "childhood home",
            "homestead", "founding", "settlement", "colonial", "ruins", "civil rights",
            "commemorat"
        ]
    ):
        is_historic = True

    if is_historic:
        tags.append("Historic")

    # 3. Cultural
    is_cultural = False
    if any(
        t in topics_lower
        for t in [
            "arts", "music", "literature", "native american heritage", "african american heritage",
            "asian american heritage", "hispanic american heritage", "latino american heritage",
            "pacific islander heritage", "indigenous peoples", "cultural demonstrations",
            "traditions", "folklore", "religion and spirituality", "civil rights",
            "social movements", "education", "literature and writers", "theater and performing arts",
            "crafts"
        ]
    ):
        is_cultural = True
    elif any(
        kw in text_corpus
        for kw in [
            "culture", "cultural", "native american", "indigenous", "tribe", "tribal",
            "ancestral", "pueblo", "tradition", "ceremonial", "art", "music", "literature",
            "civil rights", "equality", "movement", "folklore"
        ]
    ):
        is_cultural = True

    if is_cultural:
        tags.append("Cultural")

    # 4. Building
    is_building = False
    if any(
        t in topics_lower
        for t in [
            "architecture and building", "engineering", "lighthouses", "forts", "dams",
            "bridges", "birthplace", "homes and homesteads", "inventions and inventions",
            "prisons", "mills and manufacturing", "plantations", "missions"
        ]
    ):
        is_building = True
    elif any(
        kw in text_corpus
        for kw in [
            "building", "mansion", "cabin", "cottage", "estate", "architecture",
            "lighthouse", "fort ", "fortress", "castle", "inn", "tavern", "grist mill",
            "courthouse", "chapel", "church", "cathedral", "mission", "prison"
        ]
    ):
        is_building = True

    if is_building:
        tags.append("Building")

    # 5. Nature
    is_nature = False
    nature_types = {
        "national park",
        "national park & preserve",
        "national preserve",
        "national monument & preserve",
        "national seashore",
        "national lakeshore",
        "national river",
        "national wild and scenic river",
        "national scenic river",
        "wild river",
        "national scenic trail",
        "national recreation area",
    }
    if site_type.lower() in nature_types:
        is_nature = True
    elif any(
        t in topics_lower
        for t in [
            "animals", "birds", "geology", "caves, caverns and karst", "forests and woodlands",
            "watersheds", "coasts, islands and atolls", "mountains", "canyons and canyonlands",
            "glaciers", "volcanoes", "deserts", "wetlands", "wilderness", "scenic views",
            "ecology", "fossils and paleontology", "geothermal", "night sky", "rivers and streams",
            "lakes and ponds", "oceans", "flora and fauna", "natural resources", "conservation",
            "endangered species"
        ]
    ):
        is_nature = True
    elif any(
        kw in text_corpus
        for kw in [
            "nature", "natural", "wildlife", "wilderness", "forest", "woodland", "canyon",
            "mountain", "geology", "geological", "valley", "ecosystem", "habitat", "flora",
            "fauna", "biodiversity", "glacier", "volcano", "desert", "cave", "cavern",
            "waterfall", "river", "lake", "ocean", "reef", "seashore", "lakeshore", "wetland"
        ]
    ):
        is_nature = True

    if is_nature:
        tags.append("Nature")

    # 6. Specific succinct descriptors
    # Scenic
    if "scenic" in site_type.lower() or "scenic views" in topics_lower or "scenic" in text_corpus:
        tags.append("Scenic")

    # Coastal
    if (
        "seashore" in site_type.lower()
        or any(t in topics_lower for t in ["coasts, islands and atolls", "oceans"])
        or any(kw in text_corpus for kw in ["coast", "coastal", "barrier island", "ocean", "beach", "seashore", "reef"])
    ):
        tags.append("Coastal")

    # Mountain
    if (
        "mountains" in topics_lower
        or any(kw in text_corpus for kw in ["mountain", "peaks", "alpine", "summit", "sierra", "rocky mountains"])
    ):
        tags.append("Mountain")

    # Canyon
    if (
        "canyons and canyonlands" in topics_lower
        or any(kw in text_corpus for kw in ["canyon", "gorge", "ravine"])
    ):
        tags.append("Canyon")

    # Desert
    if (
        "deserts" in topics_lower
        or any(kw in text_corpus for kw in ["desert", "sand dunes", "badlands", "arid"])
    ):
        tags.append("Desert")

    # Cave
    if (
        "caves, caverns and karst" in topics_lower
        or any(kw in text_corpus for kw in ["cave", "cavern", "karst"])
    ):
        tags.append("Cave")

    # Water
    water_keywords = ["river", "lake", "waterfall", "springs", "bay", "lagoon", "watershed"]
    if (
        any(k in site_type.lower() for k in ["river", "lakeshore"])
        or any(t in topics_lower for t in ["rivers and streams", "lakes and ponds", "watersheds"])
        or any(kw in text_corpus for kw in water_keywords)
    ):
        tags.append("Water")

    # Wildlife
    if (
        any(t in topics_lower for t in ["animals", "birds", "endangered species"])
        or any(kw in text_corpus for kw in ["wildlife", "bison", "bears", "elk", "marine life"])
    ):
        tags.append("Wildlife")

    return deduplicate_tags(tags)


def fetch_all_parks(api_key: str, limit_count: int | None = None) -> list[dict]:
    """Paginate through the NPS API until all sites are fetched."""
    headers = {"X-Api-Key": api_key}
    limit = 50
    start = 0
    all_parks = []

    print("Querying NPS API...")
    while True:
        batch_limit = limit if limit_count is None else min(limit, limit_count - len(all_parks))
        params = {"limit": batch_limit, "start": start}
        response = requests.get(BASE_URL, headers=headers, params=params, timeout=15)

        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            sys.exit(1)

        data = response.json()
        parks_batch = data.get("data", [])
        total = int(data.get("total", 0))

        if not parks_batch:
            break

        all_parks.extend(parks_batch)
        print(f"Fetched {len(all_parks)} of {total} sites...")

        if limit_count is not None and len(all_parks) >= limit_count:
            break

        start += limit
        if start >= total:
            break

    return all_parks


def build_csv(parks: list[dict], output_path: str):
    """Write parsed sites matching the requested column structure."""
    records = []
    for p in parks:
        title = p.get("fullName", "").strip()
        lat = p.get("latitude", "").strip()
        lon = p.get("longitude", "").strip()
        category = p.get("designation", "").strip() or "National Park System Unit"
        website = p.get("url", "").strip()
        city, state = extract_city_state(p)
        country = "US"
        tags_str = generate_tags(p)

        records.append(
            {
                "title": title,
                "latitude": lat,
                "longitude": lon,
                "city": city,
                "state": state,
                "category": category,
                "website": website,
                "country": country,
                "Tags": tags_str,
            }
        )

    # Sort alphabetically by Title
    records.sort(key=lambda r: r["title"])

    saved = write_standard_csv(
        output_path,
        records,
        fieldnames=[
            "title",
            "latitude",
            "longitude",
            "city",
            "state",
            "category",
            "website",
            "country",
            "Tags",
        ],
    )
    print(f"\nSuccessfully wrote {len(records)} sites with tags to '{saved}'.")


def main():
    parser = argparse.ArgumentParser(
        description="Extract all National Park Service (NPS) sites with coordinates, categorization, and tags for Vistarae."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_FILE,
        help=f"Path to output CSV file (default: {OUTPUT_FILE}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of sites to fetch (useful for quick testing).",
    )

    args = parser.parse_args()
    parks = fetch_all_parks(API_KEY, limit_count=args.limit)
    build_csv(parks, args.output)


if __name__ == "__main__":
    main()